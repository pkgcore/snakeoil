# Copyright: 2005 Marien Zwart <marienz@gentoo.org>
# License: BSD/GPL2

import os
import shutil
import sys
import tempfile

from snakeoil import modules
from snakeoil.test import TestCase


class ModulesTest(TestCase):

    def setUp(self):
        # set up some test modules for our use
        self.dir = tempfile.mkdtemp()
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

    def tearDown(self):
        # pop the test module dir from path
        sys.path.pop(0)
        # and kill it
        shutil.rmtree(self.dir)
        # make sure we don't keep the sys.modules entries around
        for i in range(3):
            sys.modules.pop('mod_test%s' % i, None)
            sys.modules.pop('mod_testpack.mod_test%s' % i, None)
        sys.modules.pop('mod_testpack', None)
        sys.modules.pop('mod_horked', None)
        sys.modules.pop('mod_testpack.mod_horked', None)

    def test_load_module(self):
        # import an already-imported module
        self.assertIdentical(
            modules.load_module('snakeoil.modules'), modules)
        # and a system one, just for kicks
        self.assertIdentical(modules.load_module('sys'), sys)
        # non-existing module from an existing package
        self.assertRaises(
            modules.FailedImport, modules.load_module, 'snakeoil.__not_there')
        # (hopefully :) non-existing top-level module/package
        self.assertRaises(
            modules.FailedImport, modules.load_module, '__not_there')

        # "Unable to import"
        # pylint: disable=F0401

        # unimported toplevel module
        modtest1 = modules.load_module('mod_test1')
        import mod_test1
        self.assertIdentical(mod_test1, modtest1)
        # unimported in-package module
        packtest2 = modules.load_module('mod_testpack.mod_test2')
        from mod_testpack import mod_test2
        self.assertIdentical(mod_test2, packtest2)

    def test_load_attribute(self):
        # already imported
        self.assertIdentical(modules.load_attribute('sys.path'), sys.path)
        # unimported
        myfoo = modules.load_attribute('mod_testpack.mod_test2.foo')

        # "Unable to import"
        # pylint: disable=F0401

        from mod_testpack.mod_test2 import foo
        self.assertIdentical(foo, myfoo)
        # nonexisting attribute
        self.assertRaises(
            modules.FailedImport,
            modules.load_attribute, 'snakeoil.froznicator')
        # nonexisting top-level
        self.assertRaises(
            modules.FailedImport, modules.load_attribute,
            'spork_does_not_exist.foo')
        # not an attr
        self.assertRaises(
            modules.FailedImport, modules.load_attribute, 'sys')
        # not imported yet
        self.assertRaises(
            modules.FailedImport,
            modules.load_attribute, 'mod_testpack.mod_test3')

    def test_load_any(self):
        # import an already-imported module
        self.assertIdentical(modules.load_any('snakeoil.modules'), modules)
        # attribute of an already imported module
        self.assertIdentical(modules.load_any('sys.path'), sys.path)
        # already imported toplevel.
        self.assertIdentical(sys, modules.load_any('sys'))
        # unimported
        myfoo = modules.load_any('mod_testpack.mod_test2.foo')

        # "Unable to import"
        # pylint: disable=F0401

        from mod_testpack.mod_test2 import foo
        self.assertIdentical(foo, myfoo)
        # nonexisting attribute
        self.assertRaises(
            modules.FailedImport, modules.load_any, 'snakeoil.froznicator')
        # nonexisting top-level
        self.assertRaises(
            modules.FailedImport, modules.load_any,
            'spork_does_not_exist.foo')
        self.assertRaises(
            modules.FailedImport, modules.load_any,
            'spork_does_not_exist')
        # not imported yet
        self.assertRaises(
            modules.FailedImport,
            modules.load_any, 'mod_testpack.mod_test3')

    def test_broken_module(self):
        for func in [modules.load_module, modules.load_any]:
            self.assertRaises(
                modules.FailedImport, func, 'mod_testpack.mod_horked')
            self.assertFalse('mod_testpack.mod_horked' in sys.modules, func)
