from copy import copy
import difflib

from ..caching import WeakInstMeta
from ..formatters import PlainTextFormatter


class Exit(Exception):
    """Used to catch parser.exit."""

    def __init__(self, status, message):
        Exception.__init__(self, message)
        self.status = status
        self.message = message


class Error(Exception):
    """Used to catch parser.error."""

    def __init__(self, message):
        Exception.__init__(self, message)
        self.message = message


def noexit(status=0, message=None):
    raise Exit(status, message)


def noerror(message=None):
    raise Error(message)


def mangle_parser(parser):
    """Make an argparser testable."""
    # Return a copy to avoid the potential of modifying what we're working on.
    parser = copy(parser)
    parser.exit = noexit
    parser.error = noerror
    parser.out = FakeStreamFormatter()
    parser.err = FakeStreamFormatter()
    return parser


class FormatterObject(metaclass=WeakInstMeta):
    __inst_caching__ = True

    def __call__(self, formatter):
        formatter.stream.write(self)


class Color(FormatterObject):
    __inst_caching__ = True

    def __init__(self, mode, color):
        self.mode = mode
        self.color = color

    def __repr__(self):
        return '<Color: mode - %s; color - %s>' % (self.mode, self.color)


class Reset(FormatterObject):
    __inst_caching__ = True

    def __repr__(self):
        return '<Reset>'


class Bold(FormatterObject):
    __inst_caching__ = True

    def __repr__(self):
        return '<Bold>'


class ListStream(list):

    def write(self, *args):
        stringlist = []
        objectlist = []
        for arg in args:
            if isinstance(arg, bytes):
                stringlist.append(arg)
            else:
                objectlist.append(b''.join(stringlist))
                stringlist = []
                objectlist.append(arg)
        objectlist.append(b''.join(stringlist))
        # We use len because boolean ops shortcircuit
        if (len(self) and isinstance(self[-1], bytes) and
                isinstance(objectlist[0], bytes)):
            self[-1] = self[-1] + objectlist.pop(0)
        self.extend(objectlist)

    def flush(self):
        """Stub function to fake flush() support."""


class FakeStreamFormatter(PlainTextFormatter):

    def __init__(self):
        PlainTextFormatter.__init__(self, ListStream([]))
        self.reset = Reset()
        self.bold = Bold()
        self.first_prefix = [None]

    def resetstream(self):
        self.stream = ListStream([])

    def fg(self, color=None):
        return Color('fg', color)

    def bg(self, color=None):
        return Color('bg', color)

    def get_text_stream(self):
        return b''.join(
            [x for x in self.stream
             if not isinstance(x, FormatterObject)]).decode('ascii')


class ArgParseMixin:
    """Provide some utility methods for testing the parser and main.

    :cvar parser: ArgumentParser subclass to test.
    :cvar main: main function to test.
    """

    def parse(self, *args, **kwargs):
        """Parse a commandline and return the Values object.

        args are passed to parse_args
        """
        return self.parser.parse_args(*args, **kwargs)

    @property
    def parser(self):
        p = copy(self._argparser)
        return mangle_parser(p)

    def get_main(self, namespace):
        return namespace.main_func

    def assertError(self, message, *args, **kwargs):
        """Pass args to the argument parser and assert it errors message."""
        try:
            self.parse(*args, **kwargs)
        except Error as e:
            assert message == e.message
        else:
            raise AssertionError('no error triggered')

    def assertExit(self, status, message, *args, **kwargs):
        """Pass args, assert they trigger the right exit condition."""
        try:
            self.parse(*args, **kwargs)
        except Exit as e:
            assert message == e.message.strip()
            assert status == e.status
        else:
            raise AssertionError('no exit triggered')

    def assertOut(self, out, *args, **kwargs):
        """Like :obj:`assertOutAndErr` but without err."""
        return self.assertOutAndErr(out, (), *args, **kwargs)

    def assertErr(self, err, *args, **kwargs):
        """Like :obj:`assertOutAndErr` but without out."""
        return self.assertOutAndErr((), err, *args, **kwargs)

    def assertOutAndErr(self, out, err, *args, **kwargs):
        """Parse options and run main.

        Extra arguments are parsed by the argument parser.

        :param out: list of strings produced as output on stdout.
        :param err: list of strings produced as output on stderr.
        """
        options = self.parse(*args, **kwargs)
        outformatter = FakeStreamFormatter()
        errformatter = FakeStreamFormatter()
        main = self.get_main(options)
        main(options, outformatter, errformatter)
        diffs = []
        for name, strings, formatter in [('out', out, outformatter),
                                         ('err', err, errformatter)]:
            actual = formatter.get_text_stream()
            if strings:
                expected = '\n'.join(strings)
            else:
                expected = ''
            if expected != actual:
                diffs.extend(difflib.unified_diff(
                    strings, actual.split('\n')[:-1],
                    'expected %s' % (name,), 'actual', lineterm=''))
        if diffs:
            raise AssertionError('\n' + '\n'.join(diffs))
        return options
