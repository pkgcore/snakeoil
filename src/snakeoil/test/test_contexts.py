# Copyright: 2015 Tim Harder <radhermit@gmail.com>
# License: GPL2/BSD 3 clause

import os
import sys

from snakeoil.contexts import chdir, syspath
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
