# Copyright: 2006-2012 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD 3 clause

import os
import signal
import sys
import time
import tempfile

try:
    from unittest import mock
except ImportError:
    import mock

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
        script_name = "findpath-test.sh"
        self.assertRaises(process.CommandNotFound,
                          process.find_binary, script_name)

        # check fallback
        self.assertEqual(
            process.find_binary(script_name, fallback=os.path.join('usr', 'bin', script_name)),
            os.path.join('usr', 'bin', script_name))

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

        # check PATH override
        tempdir = tempfile.mkdtemp(dir=self.dir)
        fp = os.path.join(tempdir, script_name)
        touch(fp)
        os.chmod(fp, 0o750)
        self.assertRaises(process.CommandNotFound, process.find_binary, fp)
        self.assertEqual(fp, process.find_binary(fp, paths=[tempdir]))

        # make sure dirs aren't returned as binaries
        self.assertRaises(
            process.CommandNotFound, process.find_binary,
            os.path.basename(self.dir), os.path.dirname(self.dir))
        self.assertRaises(
            process.CommandNotFound, process.find_binary, self.dir)


class TestIsRunning(TestCase):

    def test_is_running(self):
        # confirm we're running
        self.assertTrue(process.is_running(os.getpid()))

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
                self.assertFalse(process.is_running(pid))
            else:
                process.is_running(pid)
            os.kill(pid, signal.SIGKILL)

        with mock.patch('snakeoil.process.os.kill') as kill:
            kill.side_effect = OSError(3, 'No such process')
            self.assertRaises(
                process.ProcessNotFound, process.is_running, 1234)

            kill.side_effect = OSError(4, 'Interrupted system call')
            self.assertRaises(
                OSError, process.is_running, 1234)

        with mock.patch('snakeoil.process.open') as open:
            open.side_effect = OSError(2, 'No such file or directory')
            self.assertRaises(
                process.ProcessNotFound, process.is_running, os.getpid())

            open.side_effect = OSError(5, 'Input/output error')
            self.assertRaises(
                OSError, process.is_running, os.getpid())
