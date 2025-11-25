__all__ = ("import_submodules_of", "get_submodules_of")
import functools
import importlib
import importlib.machinery
import os
import pathlib
import types
import typing

T_class_filter = typing.Callable[[str], bool]


def get_submodules_of(
    root: types.ModuleType,
    /,
    dont_import: T_class_filter | typing.Container[str] | None = None,
    ignore_import_failures: T_class_filter | typing.Container[str] | bool = False,
) -> typing.Iterable[types.ModuleType]:
    """Visit all submodules of the target via walking the underlying filesystem

    This currently cannot work against a frozen python exe (for example), nor source only contained within an egg; it currently just walks the FS.
    :param root: the module to trace
    :param dont_import: do not try importing anything in this sequence or dont_import(qualname)
      boolean result.  Defaults to no filter
    :param ignore_import_failures: filter of what modules are known to potentially raise an
      ImportError, and to tolerate those if it occurs.  Defaults to tolerating none.
    """

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

        if current is not root:
            yield current
        base = pathlib.Path(os.path.abspath(current.__file__))
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
            else:
                for ext in importlib.machinery.all_suffixes():
                    if name.endswith(ext):
                        name = name[: -len(ext)]
                        break
                else:
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
                to_scan.append(importlib.import_module(qualname))
            except ImportError:
                if not ignore_import_failures(qualname):
                    raise


def import_submodules_of(target: types.ModuleType, **kwargs) -> None:
    """load all modules of the given namespace.

    See get_submodules_of for the kwargs options.
    """
    for _ in get_submodules_of(target, **kwargs):
        pass
