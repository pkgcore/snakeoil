import sys

import pytest

from snakeoil import modules
from snakeoil.deprecation import suppress_deprecations


class TestModules:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        # set up some test modules for our use
        packdir = tmp_path / "mod_testpack"
        packdir.mkdir()
        # create an empty file
        (packdir / "__init__.py").touch()

        for directory in (tmp_path, packdir):
            for i in range(3):
                (directory / f"mod_test{i}.py").write_text("def foo(): pass\n")
            (directory / "mod_horked.py").write_text("1/0\n")
        # append them to path
        sys.path.insert(0, str(tmp_path))

        yield

        # pop the test module dir from path
        sys.path.pop(0)
        # make sure we don't keep the sys.modules entries around
        for i in range(3):
            sys.modules.pop("mod_test%s" % i, None)
            sys.modules.pop("mod_testpack.mod_test%s" % i, None)
        sys.modules.pop("mod_testpack", None)
        sys.modules.pop("mod_horked", None)
        sys.modules.pop("mod_testpack.mod_horked", None)

    @suppress_deprecations()
    def test_load_attribute(self):
        # already imported
        assert modules.load_attribute("sys.path") is sys.path
        # unimported
        myfoo = modules.load_attribute("mod_testpack.mod_test2.foo")

        # "Unable to import"
        # pylint: disable=F0401

        from mod_testpack.mod_test2 import foo

        assert foo is myfoo
        # nonexisting attribute
        with pytest.raises(modules.FailedImport):
            modules.load_attribute("snakeoil.froznicator")
        # nonexisting top-level
        with pytest.raises(modules.FailedImport):
            modules.load_attribute("spork_does_not_exist.foo")
        # not an attr
        with pytest.raises(modules.FailedImport):
            modules.load_attribute("sys")
        # not imported yet
        with pytest.raises(modules.FailedImport):
            modules.load_attribute("mod_testpack.mod_test3")

    @suppress_deprecations()
    def test_load_any(self):
        # import an already-imported module
        assert modules.load_any("snakeoil.modules") is modules
        # attribute of an already imported module
        assert modules.load_any("sys.path") is sys.path
        # already imported toplevel.
        assert sys is modules.load_any("sys")
        # unimported
        myfoo = modules.load_any("mod_testpack.mod_test2.foo")

        # "Unable to import"
        # pylint: disable=F0401

        from mod_testpack.mod_test2 import foo

        assert foo is myfoo
        # nonexisting attribute
        with pytest.raises(modules.FailedImport):
            modules.load_any("snakeoil.froznicator")
        # nonexisting top-level
        with pytest.raises(modules.FailedImport):
            modules.load_any("spork_does_not_exist.foo")
        with pytest.raises(modules.FailedImport):
            modules.load_any("spork_does_not_exist")
        # not imported yet
        with pytest.raises(modules.FailedImport):
            modules.load_any("mod_testpack.mod_test3")

    @suppress_deprecations()
    def test_broken_module(self):
        for func in [modules.load_any]:
            with pytest.raises(modules.FailedImport):
                func("mod_testpack.mod_horked")
            assert "mod_testpack.mod_horked" not in sys.modules
