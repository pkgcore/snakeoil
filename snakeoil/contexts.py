# Copyright: 2015 Tim Harder <radhermit@gmail.com>
#
# Ideas and code for SplitExec have been borrowed from withhacks
# (https://pypi.python.org/pypi/withhacks) governed by the MIT license found
# below.
#
# Copyright (c) 2010 Ryan Kelly
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""Various with-statement context utilities."""

import errno
import inspect
import os
from multiprocessing.connection import Pipe
import sys
import threading
import traceback


class SplitExec(object):
    """Context manager separating code execution across parent/child processes.

    This is done by forking and doing some magic on the stack so the contents
    of the context are executed only on the forked child. Exceptions are
    pickled and passed back to the parent.
    """
    def __init__(self):
        self.__trace_lock = threading.Lock()
        self.__orig_sys_trace = None
        self.__orig_trace_funcs = {}
        self.__injected_trace_funcs = {}
        self.__pipe = None
        self.childpid = None

    def parent_setup(self):
        """Initialization for parent process."""

    def child_setup(self):
        """Initialization for child process."""

    def cleanup(self):
        """Parent process clean up on termination of the child."""

    def exception_cleanup(self):
        """Parent process clean up after the child throws an exception."""
        self.cleanup()

    def __enter__(self):
        parent_pipe, child_pipe = Pipe()
        childpid = os.fork()

        if childpid != 0:
            self.parent_setup()
            self.childpid = childpid
            self.__pipe = parent_pipe
            frame = self.__get_context_frame()
            self.__inject_trace_func(frame, self.__exit_context)

            return self

        else:
            self.__pipe = child_pipe

            try:
                self.child_setup()

            # pylint: disable=W0703
            # need to catch all exceptions here since we are passing them to
            # the parent process
            except Exception as e:
                e.__traceback_list__ = traceback.format_exc()
                self.__pipe.send(e)
                try:
                    self.__pipe.send(SystemExit())
                except (BrokenPipeError if sys.hexversion >= 0x03030000  # pylint: disable=E0602
                        else OSError, IOError) as e:
                    if e.errno in (errno.EPIPE, errno.ESHUTDOWN):
                        pass
                    else:
                        raise
                os._exit(0)  # pylint: disable=W0212
                # we don't want SystemExit being caught here

            return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if exc_type is self.ParentException:
            try:
                exception = self.__pipe.recv()
            except EOFError as e:
                exception = SystemExit(e)

            if not isinstance(exception, SystemExit):
                os.waitpid(self.childpid, 0)
                self.exception_cleanup()
                sys.excepthook = self.__excepthook
                raise exception

        elif exc_value is not None:
            # Unfortunately, traceback objects can't be pickled so the relevant
            # traceback from the code executing within the chroot context is
            # placed in the __traceback_list__ attribute and printed by a
            # custom exception hook.
            exc_value.__traceback_list__ = traceback.format_exc()
            self.__pipe.send(exc_value)

        if self.childpid is None:
            try:
                self.__pipe.send(SystemExit())
            except (BrokenPipeError if sys.hexversion >= 0x03030000  # pylint: disable=E0602
                    else OSError, IOError) as e:
                if e.errno in (errno.EPIPE, errno.ESHUTDOWN):
                    pass
                else:
                    raise
            os._exit(0)  # pylint: disable=W0212

        # wait for child process to exit
        os.waitpid(self.childpid, 0)
        self.cleanup()

        return True

    @staticmethod
    def __excepthook(_exc_type, exc_value, exc_traceback):
        """Output the proper traceback information from the chroot context."""
        if hasattr(exc_value, '__traceback_list__'):
            sys.stderr.write(exc_value.__traceback_list__)
        else:
            traceback.print_tb(exc_traceback)

    @staticmethod
    def __dummy_sys_trace(*args, **_kwargs):
        """Dummy trace function used to enable tracing."""

    class ParentException(Exception):
        """Exception used to detect when the child terminates."""

    def __enable_tracing(self):
        """Enable system-wide tracing.

        If tracing is already enabled nothing is done.
        """
        try:
            self.__orig_sys_trace = sys.gettrace()
        except AttributeError:
            self.__orig_sys_trace = None
        if self.__orig_sys_trace is None:
            sys.settrace(self.__dummy_sys_trace)

    def __disable_tracing(self):
        """Disable system-wide tracing, if it was specifically switched on."""
        if self.__orig_sys_trace is None:
            sys.settrace(None)

    def __exit_context(self, _frame):
        """Simple function to throw a ParentException."""
        raise self.ParentException()

    def __inject_trace_func(self, frame, func):
        """Inject a trace function for a frame.

        The given trace function will be executed immediately when the frame's
        execution resumes.
        """
        with self.__trace_lock:
            if frame.f_trace is not self.__invoke_trace_funcs:
                self.__orig_trace_funcs[frame] = frame.f_trace
                frame.f_trace = self.__invoke_trace_funcs
                self.__injected_trace_funcs[frame] = []
                if len(self.__orig_trace_funcs) == 1:
                    self.__enable_tracing()
        self.__injected_trace_funcs[frame].append(func)

    def __invoke_trace_funcs(self, frame, *_args, **_kwargs):
        """Invoke all trace funcs that have been injected.

        Once the injected functions have been executed all trace hooks are
        removed in order to minimize overhead.
        """
        try:
            for func in self.__injected_trace_funcs[frame]:
                func(frame)
        finally:
            del self.__injected_trace_funcs[frame]
            with self.__trace_lock:
                if len(self.__orig_trace_funcs) == 1:
                    self.__disable_tracing()
                frame.f_trace = self.__orig_trace_funcs.pop(frame)

    def __get_context_frame(self):
        """Get the frame object for the with-statement context.

        This is designed to work from within superclass method call. It finds
        the first frame where the local variable "self" doesn't exist.
        """
        try:
            return self.__frame

        except AttributeError:
            # an offset of two accounts for this method and its caller
            frame = inspect.stack(0)[2][0]

            while frame.f_locals.get('self') is self:
                frame = frame.f_back
            self.__frame = frame  # pylint: disable=W0201
            return frame
