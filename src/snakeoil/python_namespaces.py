__all__ = ("import_submodules_of", "get_submodules_of")

import contextlib
import os
import sys
import types
import typing
from importlib import import_module, invalidate_caches, machinery
from importlib import util as import_util
from pathlib import Path

T_class_filter = typing.Callable[[str], bool]


def get_submodules_of(
    root: types.ModuleType | str,
    /,
    dont_import: T_class_filter | typing.Container[str] | None = None,
    ignore_import_failures: T_class_filter | typing.Container[str] | bool = False,
    include_root=False,
) -> typing.Iterable[types.ModuleType]:
    """Visit all submodules of the target finding modules ending with PEP3147 suffixes.

    This currently cannot work against a frozen python exe (for example), nor source only contained within an egg; it currently just walks the FS.
    :param root: the module to trace
    :param dont_import: do not try importing anything in this sequence or dont_import(qualname)
      boolean result.  Defaults to no filter
    :param ignore_import_failures: filter of what modules are known to potentially raise an
      ImportError, and to tolerate those if it occurs.  Defaults to tolerating none.
    """

    if isinstance(root, str):
        root = import_module(root)

    if dont_import is None:
        dont_import = lambda _: False  # noqa: E731
    elif isinstance(dont_import, typing.Container):
        dont_import = dont_import.__contains__

    if ignore_import_failures is True:
        ignore_import_failures = bool
    elif ignore_import_failures is False:
        ignore_import_failures = lambda x: False  # noqa: E731
    elif isinstance(ignore_import_failures, typing.Container):
        ignore_import_failures = ignore_import_failures.__contains__

    to_scan = [root]
    while to_scan:
        current = to_scan.pop()
        if current.__file__ is None:
            raise ValueError(
                f"module {current!r} lacks __file__ attribute.  If this is a PEP420 namespace module, that is unsupported currently"
            )

        if current is not root or include_root:
            yield current
        base = Path(os.path.abspath(current.__file__))
        # if it's not the root of a module, there's nothing to do- return it..
        if not base.name.startswith("__init__."):
            continue
        for potential in base.parent.iterdir():
            name = potential.name
            qualname = f"{current.__name__}.{name.split('.', 1)[0]}"
            if name.startswith("__init__."):
                # if we're in this directory, we already imported the enclosing namespace.
                continue
            if potential.is_dir():
                if name == "__pycache__":
                    continue
            elif remove_py_extension(name) is None:
                # it's not a python source.
                continue

            if dont_import(qualname):
                continue

            try:
                # intentionally re-examine it; for a file tree this is wasteful since
                # we would know if it's a directory or not, but whenever this code gets
                # extended for working from .whl or .egg directly, we will want that
                # logic in one spot. TL;DR: this is intentionally not optimized for the
                # common case.
                to_scan.append(import_module(qualname))
            except ImportError as e:
                if not ignore_import_failures(qualname):
                    raise ImportError(f"failed importing {qualname}: {e}") from e


def import_submodules_of(target: types.ModuleType, **kwargs) -> None:
    """load all modules of the given namespace.

    See get_submodules_of for the kwargs options.
    """
    for _ in get_submodules_of(target, **kwargs):
        pass


def remove_py_extension(path: Path | str) -> str | None:
    """Return the stem of a path or None, if the extension is PEP3147 (.py, .pyc, etc)

    This accounts for the fact certain extensions in importlib.machinery.all_suffixes()
    intersect each other.  This will give you the resultant package name irregardless of
    PEP3147 conflicts.

    If it's not a valid extension, None is returned.
    """
    name = Path(path).name
    for ext in sorted(machinery.all_suffixes(), key=lambda x: x.split(".")):
        if name.endswith(ext):
            return name[: -len(ext)]
    return None


@contextlib.contextmanager
def protect_imports() -> typing.Generator[
    tuple[list[str], dict[str, types.ModuleType]], None, None
]:
    """
    Non threadsafe mock.patch of internal imports to allow revision

    This should used in tests or very select scenarios.  Assume that underlying
    c extensions that hold internal static state (curse module) will reimport, but
    will not be 'clean'.  Any changes an import inflicts on the other modules in
    memory, etc, this cannot block that.  Nor is this intended to do so; it's
    for controlled tests or very specific usages.
    """
    orig_content = sys.path[:]
    orig_modules = sys.modules.copy()
    with contextlib.nullcontext():
        yield sys.path, sys.modules

    sys.path[:] = orig_content
    # This is explicitly not thread safe, but manipulating sys.path fundamentally isn't thus this context
    # isn't thread safe.  TL;dr: nuke it, and restore, it's the only way to be sure (to paraphrase)
    sys.modules.clear()
    sys.modules.update(orig_modules)
    # Out of paranoia, force loaders to reset their caches.
    invalidate_caches()


def import_module_from_path(
    path: str | Path, module_name: str | None = None
) -> types.ModuleType:
    """Load and return a module from a file path, without needing a package.

    :param path: the path to load.  No python package structure will be inferred from this.  Currently it
      must end in a python extension.
    :param module_name:  If given, this is __name__ within the module.  If not given it is
      inferred from path if path has a valid python extension.  If it does not, an ImportError
      is raised and you must specify module_name yourself.
    """
    if (default_module_name := remove_py_extension(path)) is None:
        raise ValueError(f"{path} must end in a valid python extension like .py")

    module_name = default_module_name if module_name is None else module_name

    spec = import_util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create import spec for {path}")

    module = import_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
