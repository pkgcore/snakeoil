"""Generic support for running commandline tools."""

import logging
import io
import os
import sys
import traceback
from contextlib import nullcontext
from functools import partial
from signal import signal, SIGPIPE, SIG_DFL, SIGINT

from .exceptions import ExitException, find_user_exception
from .. import formatters
from ..log import suppress_logging


class Tool:
    """Abstraction for commandline tools."""

    def __init__(self, parser, outfile=None, errfile=None):
        """Initialize the utility to run.

        :type parser: :obj:`ArgumentParser` subclass instance
        :param parser: argparser instance defining valid arguments for the given tool.
        :type outfile: file-like object
        :param outfile: File to use for stdout, defaults to C{sys.stdout}.
        :type errfile: file-like object
        :param errfile: File to use for stderr, defaults to C{sys.stderr}.
        """
        if parser is None:
            raise ValueError("invalid argparser")
        self.parser = parser
        self.options = None

        if outfile is None:
            if not sys.stdout.isatty() and sys.stdout == sys.__stdout__:
                # if redirecting/piping stdout use line buffering, skip if
                # stdout has been set to some non-standard object
                outfile = os.fdopen(sys.stdout.fileno(), 'w', 1)
            else:
                outfile = sys.stdout
        if errfile is None:
            errfile = sys.stderr

        out_fd = err_fd = None
        if hasattr(outfile, 'fileno') and hasattr(errfile, 'fileno'):
            # annoyingly, fileno can exist but through unsupport
            try:
                out_fd, err_fd = outfile.fileno(), errfile.fileno()
            except (io.UnsupportedOperation, IOError):
                pass

        if out_fd is not None and err_fd is not None:
            out_stat, err_stat = os.fstat(out_fd), os.fstat(err_fd)
            if out_stat.st_dev == err_stat.st_dev \
                    and out_stat.st_ino == err_stat.st_ino and \
                    not errfile.isatty():
                # they're the same underlying fd.  thus
                # point the handles at the same so we don't
                # get intermixed buffering issues.
                errfile = outfile

        self._outfile = outfile
        self._errfile = errfile
        self.out = self.parser.out = formatters.PlainTextFormatter(outfile)
        self.err = self.parser.err = formatters.PlainTextFormatter(errfile)
        self.out.verbosity = self.err.verbosity = getattr(self.parser, 'verbosity', 0)

    def __call__(self, args=None):
        """Run the utility.

        :type args: sequence of strings
        :param args: arguments to parse, defaulting to C{sys.argv[1:]}.
        """
        self.args = args

        # run script and return exit status
        try:
            ret = self.main()
        except ExitException as e:
            if self.parser.debug:
                raise
            if isinstance(e.code, str):
                self.err.error(e.code)
                e.code = 1
            ret = e.code

        return ret

    def parse_args(self, args=None, namespace=None):
        """Parse the given arguments using argparse.

        :type args: sequence of strings
        :param args: arguments to parse, defaulting to C{sys.argv[1:]}.
        :type namespace: argparse.Namespace object
        :param namespace: Namespace object to use for created attributes.
        """
        try:
            self.pre_parse(args, namespace)
            options = self.parser.parse_args(args=args, namespace=namespace)
            main_func = options.pop('main_func', None)
            if main_func is None:
                raise RuntimeError("argparser missing main method")

            # reconfigure formatters for colored output if enabled
            if getattr(options, 'color', True):
                formatter_factory = partial(
                    formatters.get_formatter, force_color=getattr(options, 'color', False))
                self.out = formatter_factory(self._outfile)
                self.err = formatter_factory(self._errfile)

            # reconfigure formatters with properly parsed output verbosity
            self.out.verbosity = self.err.verbosity = getattr(options, 'verbosity', 0)

            if logging.root.handlers:
                # Remove the default handler.
                logging.root.handlers.pop(0)
            logging.root.addHandler(FormattingHandler(self.err))

            options = self.post_parse(options)
            return options, main_func
        except Exception as e:
            # handle custom execution-related exceptions
            self.handle_exec_exception(e)

    def pre_parse(self, args, namespace):
        """Handle custom options before argparsing."""

    def post_parse(self, options):
        """Handle custom options after argparsing."""
        return options

    def handle_exec_exception(self, e):
        """Handle custom runtime exceptions."""
        if self.parser.debug:
            raise
        # output user error if one exists otherwise show debugging traceback
        exc = find_user_exception(e)
        if exc is not None:
            # allow exception attribute to override user verbosity level
            if getattr(exc, '_verbosity', None) is not None:
                verbosity = exc._verbosity
            else:
                verbosity = getattr(self.parser, 'verbosity', 0)
            # output verbose error message if it exists
            if verbosity > 0:
                msg = exc.msg(verbosity).strip('\n')
                if msg:
                    self.err.write(msg)
                    raise SystemExit
            self.parser.error(exc)
        raise

    def main(self):
        """Execute the main script function."""
        exitstatus = -10

        # ignore broken pipes
        signal(SIGPIPE, SIG_DFL)

        # suppress warning level log output and below in quiet mode
        if self.parser.verbosity >= 0 or self.parser.debug:
            suppress_warnings = nullcontext()
        else:
            suppress_warnings = suppress_logging(logging.WARNING)

        try:
            with suppress_warnings:
                self.options, func = self.parse_args(args=self.args, namespace=self.options)
                exitstatus = func(self.options, self.out, self.err)
        except SystemExit as e:
            # handle argparse or other third party modules using sys.exit internally
            exitstatus = e.code
        except KeyboardInterrupt:
            self._errfile.write('keyboard interrupted- exiting')
            if self.parser.debug:
                self._errfile.write('\n')
                traceback.print_exc()
            signal(SIGINT, SIG_DFL)
            os.killpg(os.getpgid(0), SIGINT)
        except Exception as e:
            # handle custom execution-related exceptions
            self.out.flush()
            self.err.flush()
            self.handle_exec_exception(e)

        if self.options is not None:
            # set terminal title on exit
            if exitstatus:
                self.out.title(f'{self.options.prog} failed')
            else:
                self.out.title(f'{self.options.prog} succeeded')

        return exitstatus


class FormattingHandler(logging.Handler):
    """Logging handler printing through a formatter."""

    def __init__(self, formatter):
        logging.Handler.__init__(self)
        # "formatter" clashes with a Handler attribute.
        self.out = formatter

    def emit(self, record):
        if record.levelno >= logging.ERROR:
            color = 'red'
        elif record.levelno >= logging.WARNING:
            color = 'yellow'
        else:
            color = 'cyan'
        first_prefix = (self.out.fg(color), self.out.bold, record.levelname,
                        self.out.reset, ' ', record.name, ': ')
        later_prefix = (len(record.levelname) + len(record.name)) * ' ' + ' : '
        self.out.first_prefix.extend(first_prefix)
        self.out.later_prefix.append(later_prefix)
        try:
            for line in self.format(record).split('\n'):
                self.out.write(line, wrap=True)
        except Exception:
            self.handleError(record)
        finally:
            self.out.later_prefix.pop()
            for i in range(len(first_prefix)):
                self.out.first_prefix.pop()
