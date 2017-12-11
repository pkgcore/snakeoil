# Copyright: 2015 Tim Harder <radhermit@gmail.com>
# License: GPL2/BSD 3 clause

import errno
import os
import random
import sys
import unittest

from snakeoil.contexts import chdir, syspath, SplitExec
from snakeoil.test.mixins import TempDirMixin


class TestContexts(TempDirMixin):

    def test_chdir(self):
        orig_cwd = os.getcwd()

        with chdir(self.dir):
            self.assertNotEqual(orig_cwd, os.getcwd())

        self.assertEqual(orig_cwd, os.getcwd())

    def test_syspath(self):
        orig_syspath = tuple(sys.path)

        # by default the path gets inserted as the first element
        with syspath(self.dir):
            self.assertNotEqual(orig_syspath, tuple(sys.path))
            self.assertEqual(self.dir, sys.path[0])

        self.assertEqual(orig_syspath, tuple(sys.path))

        # insert path in a different position
        with syspath(self.dir, position=1):
            self.assertNotEqual(orig_syspath, tuple(sys.path))
            self.assertNotEqual(self.dir, sys.path[0])
            self.assertEqual(self.dir, sys.path[1])

        # conditional insert and nested context managers
        with syspath(self.dir, condition=(self.dir not in sys.path)):
            mangled_syspath = tuple(sys.path)
            self.assertNotEqual(orig_syspath, mangled_syspath)
            self.assertEqual(self.dir, sys.path[0])
            # dir isn't added again due to condition
            with syspath(self.dir, condition=(self.dir not in sys.path)):
                self.assertEqual(mangled_syspath, tuple(sys.path))


class TestSplitExec(unittest.TestCase):

    def test_context_process(self):
        # code inside the with statement is run in a separate process
        pid = os.getpid()
        with SplitExec() as c:
            pass
        self.assertIsNotNone(c.childpid)
        self.assertNotEqual(pid, c.childpid)

    def test_context_exit_status(self):
        # exit status of the child process is available as a context attr
        exit_status = random.randint(1, 255)
        with SplitExec() as c:
            os._exit(exit_status)
        self.assertEqual(c.exit_status, exit_status)

    def test_context_locals(self):
        # code inside the with statement returns modified, pickleable locals
        # via 'locals' attr of the context manager
        a = 1
        with SplitExec() as c:
            self.assertEqual(a, 1)
            a = 2
            self.assertEqual(a, 2)
            b = 3
        # changes to locals aren't propagated back
        self.assertEqual(a, 1)
        self.assertNotIn('b', locals())
        # but they're accessible via the 'locals' attr
        self.assertEqual(c.locals, {'a': 2, 'b': 3})

        # make sure unpickleables don't cause issues
        with SplitExec() as c:
            func = lambda x: x
            import sys
            a = 4
        self.assertEqual(c.locals, {'a': 4})

    def test_context_exceptions(self):
        # exceptions in the child process are sent back to the parent and re-raised
        with self.assertRaises(IOError) as cm:
            with SplitExec() as c:
                raise IOError(errno.EBUSY, 'random error')
        self.assertEqual(cm.exception.errno, errno.EBUSY)

    def test_child_setup_raises_exception(self):
        class ChildSetupException(SplitExec):
            def _child_setup(self):
                raise IOError(errno.EBUSY, 'random error')

        with self.assertRaises(IOError) as cm:
            with ChildSetupException() as c:
                pass
        self.assertEqual(cm.exception.errno, errno.EBUSY)
