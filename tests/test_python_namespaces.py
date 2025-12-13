import contextlib
import pathlib
import sys
import types
from contextlib import contextmanager
from importlib import import_module, invalidate_caches, machinery
from typing import Any, NamedTuple

import pytest

from snakeoil.python_namespaces import (
    get_submodules_of,
    import_module_from_path,
    import_submodules_of,
    protect_imports,
    remove_py_extension,
)


def write_tree(base: pathlib.Path, *paths: str | pathlib.Path):
    base.mkdir(exist_ok=True)
    for path in sorted(paths):
        path = base / pathlib.Path(path)
        if not path.parent.exists():
            path.parent.mkdir(parents=True)
        path.touch()


class test_python_namespaces:
    @contextmanager
    def protect_modules(self, base):
        python_path = sys.path[:]
        modules = sys.modules.copy()
        try:
            sys.path.append(str(base))
            invalidate_caches()
            yield (modules.copy())
        finally:
            sys.path[:] = python_path
            sys.modules = modules
            invalidate_caches()

    def test_get_submodules_of(self, tmp_path):
        write_tree(
            tmp_path,
            "_ns_test/__init__.py",
            "_ns_test/blah.py",
            "_ns_test/ignored",
            "_ns_test/real/__init__.py",
            "_ns_test/real/extra.py",
        )

        def get_it(target, *args, force_string=False, **kwargs):
            if not force_string:
                target = import_module(target)
            return list(
                sorted(x.__name__ for x in get_submodules_of(target, *args, **kwargs))
            )

        with self.protect_modules(tmp_path):
            assert ["_ns_test.blah", "_ns_test.real", "_ns_test.real.extra"] == get_it(
                "_ns_test",
                force_string=False,  # flex that it also takes strings, not just a module
            )
            assert "_ns_test" in sys.modules

            assert ["_ns_test.blah", "_ns_test.real"] == get_it(
                "_ns_test", dont_import=["_ns_test.real.extra"]
            )
            assert ["_ns_test.blah"] == get_it(
                "_ns_test", dont_import="_ns_test.real".__eq__
            ), (
                "dont_import filter failed to prevent scanning a submodule and it's children"
            )
            assert ["_ns_test.blah", "_ns_test.real"] == get_it(
                "_ns_test", dont_import="_ns_test.real.extra".__eq__
            )

            assert ["_ns_test.real", "_ns_test.real.extra"] == get_it(
                "_ns_test.real", include_root=True
            )

    def test_load(self, tmp_path):
        write_tree(
            pathlib.Path(tmp_path) / "_ns_test",
            "__init__.py",
            "blah.py",
            "foon.py",
            "extra.py",
        )
        with self.protect_modules(tmp_path):
            assert None is import_submodules_of(import_module("_ns_test"))
            assert set(["_ns_test.blah", "_ns_test.foon", "_ns_test.extra"]) == set(
                x for x in sys.modules if x.startswith("_ns_test.")
            )

    def test_import_failures(self, tmp_path):
        base = pathlib.Path(tmp_path) / "_ns_test"
        write_tree(base, "__init__.py", "blah.py")

        with (base / "bad1.py").open("w") as f:
            f.write("raise ImportError('bad1')")
        with (base / "bad2.py").open("w") as f:
            f.write("raise ImportError('bad2')")

        with self.protect_modules(tmp_path):
            mod = import_module("_ns_test")
            with pytest.raises(ImportError) as capture:
                import_submodules_of(mod, ignore_import_failures=["_ns_test.bad2"])
            assert "bad1" in " ".join(tuple(capture.value.args))

            with pytest.raises(ImportError) as capture:
                import_submodules_of(mod, ignore_import_failures=["_ns_test.bad1"])
            assert "bad2" in " ".join(tuple(capture.value.args))

            with pytest.raises(ImportError):
                import_submodules_of(mod, ignore_import_failures=False)

            assert ["_ns_test.blah"] == [
                x.__name__ for x in get_submodules_of(mod, ignore_import_failures=True)
            ]


def test_remove_py_extension():
    """Test to verify remove_py_extension strips the longest suffix."""
    conflict_long = None
    for ext in (suffixes := machinery.all_suffixes()):
        # remember, ext is '.py' or similar. Thus 2- ['', 'py']
        if len(chunked := ext.split(".")) > 2:
            if (conflict_short := f".{chunked[-1]}") in suffixes:
                conflict_long = ext
                break
    else:
        pytest.skip(
            "The interpretter has no self-conflicting python source extensions."
        )

    assert "blah" == remove_py_extension(f"blah{conflict_long}")
    assert "blah" == remove_py_extension(f"blah{conflict_short}")
    assert f"blah{conflict_short}" == remove_py_extension(f"blah{conflict_short}.py"), (
        "the code is double stripping suffixes"
    )
    assert None is remove_py_extension("asdf")
    assert None is remove_py_extension("asdf.txt")


@contextlib.contextmanager
def assert_protect_modules():
    # cpython has notes that swapping the object may result in unexpected behavior- thus
    # assert we don't.
    orig_modules_content = (orig_modules := sys.modules).copy()
    orig_path_content = (orig_path := sys.path)[:]
    with protect_imports() as (path, modules):
        assert orig_path is sys.path
        assert orig_path is path
        assert orig_path_content == path
        assert orig_modules is sys.modules
        assert orig_modules is modules
        assert orig_modules_content == modules
        yield (path, modules)

    assert orig_modules is sys.modules, "sys.modules isn't the same object"
    assert not set(orig_modules_content).symmetric_difference(sys.modules), (
        "sys.modules wasn't reset to it's original content"
    )
    assert orig_path is sys.path, "sys.path isn't the same object"
    assert orig_path_content == sys.path, (
        "sys.path content wasn't reset to it's original content"
    )


def test_protect_imports(tmp_path):
    p = tmp_path / "_must_not_exist.py"
    p.touch()
    with assert_protect_modules() as (path, modules):
        with pytest.raises(ModuleNotFoundError):
            # confirm we're not somehow intersecting something elsewhere
            import_module(p.stem)

        # also validate assert_protect_module while we're at it- thus the extra
        # checks.
        path.append(str(tmp_path))
        assert str(tmp_path) == sys.path[-1]
        import_module(p.stem)
        assert p.stem in modules
        assert p.stem in sys.modules


class ShouldBeReachedOnlyInSuccess(Exception): ...


class params(NamedTuple):
    name: str
    module_name: str = ""
    throws: type[Exception] = ShouldBeReachedOnlyInSuccess
    content: str = ""
    attrs: dict[str, Any] = {}


@pytest.mark.parametrize(
    "config",
    [
        params("blah.py", "blah"),
        params("asdf", throws=ValueError),
        # enforce override
        params("blah.py", module_name="asdf"),
        params(
            "blah.py",
            throws=DeprecationWarning,
            content="raise DeprecationWarning()",
        ),
        params("foon.py", "foon", content='x="value";y=2', attrs=dict(x="value", y=2)),
        # basic validation of pass through of underlying python machinery failure
        params("foon.py", "foon", content="fda=", throws=SyntaxError),
    ],
)
def test_import_module_from_path(tmp_path, config):
    p = tmp_path / config.name

    with p.open("w") as f:
        f.write(config.content)

    with assert_protect_modules():
        # there's a trick here; either the exception required gets thrown, or
        # we terminate the "success" path via throwing the default exception, thus
        # making that 'fine'.  For code expecting a different exception, our default throw
        # flags them as not matching the assertion.
        with pytest.raises(config.throws):
            module = import_module_from_path(p, config.module_name)
            assert isinstance(module, types.ModuleType)
            assert config.module_name == module.__name__
            assert str(p) == module.__file__
            for k, v in config.attrs.items():
                # Let fly the AttributeError- if it occurs, it's because the test is faulty.
                assert v == getattr(module, k)
            raise ShouldBeReachedOnlyInSuccess()
