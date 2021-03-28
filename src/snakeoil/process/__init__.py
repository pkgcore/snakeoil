# Copyright 2014 The Chromium OS Authors. All rights reserved. (get_exit_status and exit_as_status)

"""Process related utilities."""

import errno
import os
import signal
import sys
import time

from ..osutils import access


def find_binary(binary, paths=None, fallback=None):
    """look through the PATH environment, finding the binary to execute"""

    if os.path.isabs(binary):
        if not (os.path.isfile(binary) and access(binary, os.X_OK)):
            raise CommandNotFound(binary)
        return binary

    if paths is None:
        paths = os.environ.get("PATH", "").split(":")

    for path in paths:
        filename = os.path.join(os.path.abspath(path), binary)
        if access(filename, os.X_OK) and os.path.isfile(filename):
            return filename

    if fallback is not None:
        return fallback

    raise CommandNotFound(binary)


def get_exit_status(status):
    """Get the exit status of a child from an os.waitpid call.

    Args:
        status: The return value of os.waitpid(pid, 0)[1]

    Returns:
        The exit status of the process. If the process exited with a signal,
        the return value will be 128 plus the signal number.
    """
    if os.WIFSIGNALED(status):
        return 128 + os.WTERMSIG(status)
    else:
        assert os.WIFEXITED(status), 'Unexpected exit status %r' % status
        return os.WEXITSTATUS(status)


def exit_as_status(status):
    """Exit the same way as |status|.

    If the status field says it was killed by a signal, then we'll do that to
    ourselves.  Otherwise we'll exit with the exit code.

    See http://www.cons.org/cracauer/sigint.html for more details.

    Args:
        status: A status as returned by os.wait type funcs.
    """
    exit_status = os.WEXITSTATUS(status)

    if os.WIFSIGNALED(status):
        # Kill ourselves with the same signal.
        sig_status = os.WTERMSIG(status)
        pid = os.getpid()
        os.kill(pid, sig_status)
        time.sleep(0.1)

        # Still here?  Maybe the signal was masked.
        try:
            signal.signal(sig_status, signal.SIG_DFL)
        except RuntimeError as e:
            if e.args[0] != errno.EINVAL:
                raise
        os.kill(pid, sig_status)
        time.sleep(0.1)

        # Still here?  Just exit.
        exit_status = 127

    # Exit with the code we want.
    sys.exit(exit_status)


class CommandNotFound(Exception):

    def __init__(self, command):
        super().__init__(f'failed to find binary: {command!r}')
        self.command = command


class ProcessNotFound(Exception):

    def __init__(self, pid):
        super().__init__(f'nonexistent process: {pid}')


def _native_closerange(from_fd, to_fd):
    for fd in range(from_fd, to_fd):
        try:
            os.close(fd)
        except EnvironmentError:
            pass

try:
    if os.uname()[0].lower() != 'linux':
        # the optimized closerange works for sure on linux/glibc; for others
        # whitelist expand this as needed.
        raise ImportError()
    from .._posix import closerange

    # monkey patch os.closerange with the saner version;
    # this makes subprocess.Popen calls less noisy, and slightly faster.
    # only do this if we can drop our optimized version in.
    os.closerange = closerange
except ImportError:
    closerange = getattr(os, 'closerange', _native_closerange)
