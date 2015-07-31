# Copyright: 2006-2012 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD 3 clause

import os

from snakeoil import process
from snakeoil.fileutils import touch
from snakeoil.test import TestCase, mixins

class TestFindBinary(mixins.TempDirMixin, TestCase):

    def setUp(self):
        self.orig_env = os.environ["PATH"]
        mixins.TempDirMixin.setUp(self)
        os.environ["PATH"] = ":".join([self.dir] + self.orig_env.split(":"))

    def tearDown(self):
        os.environ["PATH"] = self.orig_env
        mixins.TempDirMixin.tearDown(self)

    def test_find_binary(self):
        script_name = "pkgcore-findpath-test.sh"
        self.assertRaises(process.CommandNotFound,
                          process.find_binary, script_name)
        fp = os.path.join(self.dir, script_name)
        touch(fp)
        os.chmod(fp, 0o640)
        self.assertRaises(process.CommandNotFound,
                          process.find_binary, script_name)
        self.assertRaises(process.CommandNotFound, process.find_binary, fp)
        os.chmod(fp, 0o750)
        self.assertIn(self.dir, process.find_binary(script_name))
        self.assertIn(self.dir, process.find_binary(fp))
        os.unlink(fp)

        # make sure dirs aren't returned as binaries
        self.assertRaises(
            process.CommandNotFound, process.find_binary,
            os.path.basename(self.dir), os.path.dirname(self.dir))
        self.assertRaises(
            process.CommandNotFound, process.find_binary, self.dir)
