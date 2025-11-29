import importlib
import pathlib
import sys
from contextlib import contextmanager

import pytest

from snakeoil.python_namespaces import (
    get_submodules_of,
    import_submodules_of,
)


class TestNamespaceCollector:
    def write_tree(self, base: pathlib.Path, *paths: str | pathlib.Path):
        base.mkdir(exist_ok=True)
        for path in sorted(paths):
            path = base / pathlib.Path(path)
            if not path.parent.exists():
                path.parent.mkdir(parents=True)
            path.touch()

    @contextmanager
    def protect_modules(self, base):
        python_path = sys.path[:]
        modules = sys.modules.copy()
        try:
            sys.path.append(str(base))
            importlib.invalidate_caches()
            yield (modules.copy())
        finally:
            sys.path[:] = python_path
            sys.modules = modules
            importlib.invalidate_caches()

    def test_it(self, tmp_path):
        self.write_tree(
            tmp_path,
            "_ns_test/__init__.py",
            "_ns_test/blah.py",
            "_ns_test/ignored",
            "_ns_test/real/__init__.py",
            "_ns_test/real/extra.py",
        )

        def get_it(target, *args, **kwargs):
            target = importlib.import_module(target)
            return list(
                sorted(x.__name__ for x in get_submodules_of(target, *args, **kwargs))
            )

        with self.protect_modules(tmp_path):
            assert ["_ns_test.blah", "_ns_test.real", "_ns_test.real.extra"] == get_it(
                "_ns_test"
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
        self.write_tree(
            pathlib.Path(tmp_path) / "_ns_test",
            "__init__.py",
            "blah.py",
            "foon.py",
            "extra.py",
        )
        with self.protect_modules(tmp_path):
            assert None is import_submodules_of(importlib.import_module("_ns_test"))
            assert set(["_ns_test.blah", "_ns_test.foon", "_ns_test.extra"]) == set(
                x for x in sys.modules if x.startswith("_ns_test.")
            )

    def test_import_failures(self, tmp_path):
        base = pathlib.Path(tmp_path) / "_ns_test"
        self.write_tree(base, "__init__.py", "blah.py")

        with (base / "bad1.py").open("w") as f:
            f.write("raise ImportError('bad1')")
        with (base / "bad2.py").open("w") as f:
            f.write("raise ImportError('bad2')")

        with self.protect_modules(tmp_path):
            mod = importlib.import_module("_ns_test")
            with pytest.raises(ImportError) as capture:
                import_submodules_of(mod, ignore_import_failures=["_ns_test.bad2"])
            assert ("bad1",) == tuple(capture.value.args)

            with pytest.raises(ImportError) as capture:
                import_submodules_of(mod, ignore_import_failures=["_ns_test.bad1"])
            assert ("bad2",) == tuple(capture.value.args)

            with pytest.raises(ImportError):
                import_submodules_of(mod, ignore_import_failures=False)

            assert ["_ns_test.blah"] == [
                x.__name__ for x in get_submodules_of(mod, ignore_import_failures=True)
            ]
