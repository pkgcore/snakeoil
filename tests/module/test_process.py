import os
import signal
import sys
import time
import tempfile
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


class TestIsRunning:

    def test_is_running(self):
        # confirm we're running
        assert process.is_running(os.getpid())

        # fork a new process, SIGSTOP it, and confirm it's not running
        pid = os.fork()
        if pid == 0:
            os.kill(os.getpid(), signal.SIGSTOP)
        else:
            # wait for signal to propagate
            time.sleep(1)
            # The return value is reliable only on Linux, on other systems just
            # make sure ProcessNotFound isn't thrown.
            if sys.platform.startswith('linux'):
                assert not process.is_running(pid)
            else:
                process.is_running(pid)
            os.kill(pid, signal.SIGKILL)

        with mock.patch('snakeoil.process.os.kill') as kill:
            kill.side_effect = OSError(3, 'No such process')
            with pytest.raises(process.ProcessNotFound):
                process.is_running(1234)

            kill.side_effect = OSError(4, 'Interrupted system call')
            with pytest.raises(OSError):
                process.is_running(1234)

        with mock.patch('builtins.open') as open:
            open.side_effect = OSError(2, 'No such file or directory')
            with pytest.raises(process.ProcessNotFound):
                process.is_running(os.getpid())

            open.side_effect = OSError(5, 'Input/output error')
            with pytest.raises(OSError):
                process.is_running(os.getpid())
