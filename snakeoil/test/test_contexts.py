# Copyright: 2015 Tim Harder <radhermit@gmail.com>
# License: GPL2/BSD 3 clause

import os

from snakeoil.contexts import chdir
from snakeoil.test.mixins import TempDirMixin


class TestChdir(TempDirMixin):

    def test_chdir(self):
        orig_cwd = os.getcwd()

        with chdir(self.dir):
            self.assertNotEqual(orig_cwd, os.getcwd())

        self.assertEqual(orig_cwd, os.getcwd())
