import os
import signal
import sys
import tempfile
import time
from unittest import mock

import pytest
from snakeoil import process
from snakeoil.fileutils import touch
from snakeoil.test.fixtures import TempDir


class TestFindBinary(TempDir):

    def setup(self):
        self.orig_path = os.environ["PATH"]
        self.script = "findpath-test.sh"
        os.environ["PATH"] = ":".join([self.dir] + self.orig_path.split(":"))

    def teardown(self):
        os.environ["PATH"] = self.orig_path

    def test_found(self):
        fp = os.path.join(self.dir, self.script)
        touch(fp)
        os.chmod(fp, 0o750)
        assert fp == process.find_binary(self.script)

    def test_missing(self):
        with pytest.raises(process.CommandNotFound):
            process.find_binary(self.script)

    def test_fallback(self):
        fallback = process.find_binary(self.script, fallback=os.path.join('bin', self.script))
        assert fallback == os.path.join('bin', self.script)

    def test_not_executable(self):
        fp = os.path.join(self.dir, self.script)
        touch(fp)
        os.chmod(fp, 0o640)
        with pytest.raises(process.CommandNotFound):
            process.find_binary(self.script)
        with pytest.raises(process.CommandNotFound):
            process.find_binary(fp)

    def test_path_override(self):
        # check PATH override
        tempdir = tempfile.mkdtemp(dir=self.dir)
        fp = os.path.join(tempdir, self.script)
        touch(fp)
        os.chmod(fp, 0o750)
        with pytest.raises(process.CommandNotFound):
            process.find_binary(self.script)
        assert fp == process.find_binary(self.script, paths=[tempdir])

    def test_no_dirs(self):
        # make sure dirs aren't returned as binaries
        with pytest.raises(process.CommandNotFound):
            process.find_binary(os.path.basename(self.dir), os.path.dirname(self.dir))
        with pytest.raises(process.CommandNotFound):
            process.find_binary(self.dir)
