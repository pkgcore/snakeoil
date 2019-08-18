import os
import sys

import pytest

from snakeoil import modules
from snakeoil.test.fixtures import TempDir


class TestModules(TempDir):

    def setup(self):
        # set up some test modules for our use
        packdir = os.path.join(self.dir, 'mod_testpack')
        os.mkdir(packdir)
        # create an empty file
        open(os.path.join(packdir, '__init__.py'), 'w').close()
        for directory in [self.dir, packdir]:
            for i in range(3):
                with open(os.path.join(directory, 'mod_test%s.py' % i), 'w') as testmod:
                    testmod.write('def foo(): pass\n')
            with open(os.path.join(directory, 'mod_horked.py'), 'w') as horkedmod:
                horkedmod.write('1/0\n')

        # append them to path
        sys.path.insert(0, self.dir)

    def teardown(self):
        # pop the test module dir from path
        sys.path.pop(0)
        # make sure we don't keep the sys.modules entries around
        for i in range(3):
            sys.modules.pop('mod_test%s' % i, None)
            sys.modules.pop('mod_testpack.mod_test%s' % i, None)
        sys.modules.pop('mod_testpack', None)
        sys.modules.pop('mod_horked', None)
        sys.modules.pop('mod_testpack.mod_horked', None)

    def test_load_module(self):
        # import an already-imported module
        assert modules.load_module('snakeoil.modules') is modules
        # and a system one, just for kicks
        assert modules.load_module('sys') is sys
        # non-existing module from an existing package
        with pytest.raises(modules.FailedImport):
            modules.load_module('snakeoil.__not_there')
        # (hopefully :) non-existing top-level module/package
        with pytest.raises(modules.FailedImport):
            modules.load_module('__not_there')

        # "Unable to import"
        # pylint: disable=F0401

        # unimported toplevel module
        modtest1 = modules.load_module('mod_test1')
        import mod_test1
        assert mod_test1 is modtest1
        # unimported in-package module
        packtest2 = modules.load_module('mod_testpack.mod_test2')
        from mod_testpack import mod_test2
        assert mod_test2 is packtest2

    def test_load_attribute(self):
        # already imported
        assert modules.load_attribute('sys.path') is sys.path
        # unimported
        myfoo = modules.load_attribute('mod_testpack.mod_test2.foo')

        # "Unable to import"
        # pylint: disable=F0401

        from mod_testpack.mod_test2 import foo
        assert foo is myfoo
        # nonexisting attribute
        with pytest.raises(modules.FailedImport):
            modules.load_attribute('snakeoil.froznicator')
        # nonexisting top-level
        with pytest.raises(modules.FailedImport):
            modules.load_attribute('spork_does_not_exist.foo')
        # not an attr
        with pytest.raises(modules.FailedImport):
            modules.load_attribute('sys')
        # not imported yet
        with pytest.raises(modules.FailedImport):
            modules.load_attribute('mod_testpack.mod_test3')

    def test_load_any(self):
        # import an already-imported module
        assert modules.load_any('snakeoil.modules') is modules
        # attribute of an already imported module
        assert modules.load_any('sys.path') is sys.path
        # already imported toplevel.
        assert sys is modules.load_any('sys')
        # unimported
        myfoo = modules.load_any('mod_testpack.mod_test2.foo')

        # "Unable to import"
        # pylint: disable=F0401

        from mod_testpack.mod_test2 import foo
        assert foo is myfoo
        # nonexisting attribute
        with pytest.raises(modules.FailedImport):
            modules.load_any('snakeoil.froznicator')
        # nonexisting top-level
        with pytest.raises(modules.FailedImport):
            modules.load_any('spork_does_not_exist.foo')
        with pytest.raises(modules.FailedImport):
            modules.load_any('spork_does_not_exist')
        # not imported yet
        with pytest.raises(modules.FailedImport):
            modules.load_any('mod_testpack.mod_test3')

    def test_broken_module(self):
        for func in [modules.load_module, modules.load_any]:
            with pytest.raises(modules.FailedImport):
                func('mod_testpack.mod_horked')
            assert 'mod_testpack.mod_horked' not in sys.modules
