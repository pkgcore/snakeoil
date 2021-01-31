"""Classes wrapping a file-like object to do fancy output on it."""

import errno
from functools import partial
import io
import locale
import os

from .klass import GetAttrProxy, steal_docs
from .mappings import defaultdictkey


__all__ = (
    "Formatter", "PlainTextFormatter", "get_formatter",
    "decorate_forced_wrapping",
)


class StreamClosed(KeyboardInterrupt):
    """Raised by :py:func:`Formatter.write` if the stream it prints to was closed.

    This inherits from :py:class:`KeyboardInterrupt` because it should usually
    be handled the same way: a common way of triggering this exception
    is by closing a pager before the script finished outputting, which
    should be handled like control+c, not like an error.
    """


# "Invalid name" (for fg and bg methods, too short)
# pylint: disable=C0103


class Formatter:
    """Abstract formatter base class.

    The types of most of the instance attributes is undefined (depends
    on the implementation of the particular Formatter subclass).

    :ivar bold: object to pass to :py:func:`write` to switch to bold mode.
    :ivar underline: object to pass to :py:func:`write` to switch to underlined mode.
    :ivar reset: object to pass to :py:func:`write` to turn off bold and underline.
    :ivar wrap: boolean indicating we auto-linewrap (defaults to off).
    :ivar autoline: boolean indicating we are in auto-newline mode
        (defaults to on).
    """

    def __init__(self):
        self.autoline = True
        self.wrap = False

    def write(self, *args, **kwargs):
        """Write something to the stream.

        Acceptable arguments are:

        * Strings are simply written to the stream.
        * None is ignored.
        * Functions are called with the formatter as argument.
          Their return value is then used the same way as the other
          arguments.
        * Formatter subclasses might special-case certain objects.

        Accepts wrap and autoline as keyword arguments. Effect is
        the same as setting them before the write call and resetting
        them afterwards.

        Accepts first_prefixes and later_prefixes as keyword
        arguments. They should be sequences that are temporarily
        appended to the first_prefix and later_prefix attributes.

        Accepts prefixes as a keyword argument. Effect is the same as
        setting first_prefixes and later_prefixes to the same value.

        Accepts first_prefix, later_prefix and prefix as keyword
        argument. Effect is the same as setting first_prefixes,
        later_prefixes or prefixes to a one-element tuple.

        The formatter has a couple of attributes that are useful as argument
        to write.
        """

    def fg(self, color=None):
        """Change foreground color.

        :param color: color to change to. A default is used if omitted.
            if passed None, resets to the default color.
        :return: object representing changing the foreground to the requested
            color, if possible for this formatter.
        """

    def bg(self, color=None):
        """Change background color.

        :param color: color to change to. A default is used if omitted.
            if passed None, resets to the default color.
        :return: object representing changing the background to the requested
            color, if possible for this formatter.
        """

    def error(self, message):
        """Format a string as an error message."""
        self.write(message, prefixes=(
            self.fg('red'), self.bold, '!!! ', self.reset))

    def warn(self, message):
        """Format a string as a warning message."""
        self.write(message, prefixes=(
            self.fg('yellow'), self.bold, '*** ', self.reset))

    def title(self, string):
        """Set the title to string"""

    def flush(self):
        """Flush the underlying stream buffer."""


class PlainTextFormatter(Formatter):
    """Formatter writing plain text to a file-like object.

    :ivar width: contains the current maximum line length.
    :ivar encoding: the encoding unicode strings should be converted to.
    :ivar first_prefix: prefixes to output at the beginning of every write.
    :ivar later_prefix: prefixes to output on each line after the first of
        every write.
    """

    bold = underline = reset = ''

    def __init__(self, stream, width=79, encoding=None):
        """Initialize.

        :type stream: file-like object.
        :param stream: stream to output to.
        :param width: maximum line width (defaults to 79).
        :param encoding: encoding unicode strings are converted to.
        """
        super().__init__()
        # We used to require a TextIOWrapper on py3. We still accept
        # one, guess the encoding from it and grab its underlying
        # bytestream.
        # It would probably be saner to shift the encoding-guessing up
        # a layer, but keep it here for backwards compat for now.
        if isinstance(stream, io.TextIOWrapper):
            self.stream = stream.buffer
        else:
            self.stream = stream
        if encoding is None:
            encoding = getattr(self.stream, 'encoding', None)
        if encoding is None:
            try:
                encoding = locale.getpreferredencoding()
            except locale.Error:
                encoding = 'ascii'
        self.encoding = encoding
        self.width = width
        self._pos = 0
        self._in_first_line = True
        self._wrote_something = False
        self.first_prefix = []
        self.later_prefix = []

    def _encoding_conversion_needed(self, val):
        return True

    def _force_encoding(self, val):
        return val.encode(self.encoding, 'replace')

    def _write_prefix(self, wrap):
        if self._in_first_line:
            prefix = self.first_prefix
        else:
            prefix = self.later_prefix
        # This is a bit braindead since it duplicates a lot of code
        # from write. Avoids fun things like word wrapped prefix though.

        for thing in prefix:
            while callable(thing):
                thing = thing(self)
            if thing is None:
                continue
            if not isinstance(thing, str):
                thing = str(thing)
            self._pos += len(thing)
            thing = self._force_encoding(thing)
            self.stream.write(thing)
        if wrap and self._pos >= self.width:
            # XXX What to do? Our prefix does not fit.
            # This makes sure we still output something,
            # but it is completely arbitrary.
            self._pos = self.width - 10

    @steal_docs(Formatter)
    def write(self, *args, **kwargs):
        wrap = kwargs.get('wrap', self.wrap)
        autoline = kwargs.get('autoline', self.autoline)
        prefixes = kwargs.get('prefixes')
        first_prefixes = kwargs.get('first_prefixes')
        later_prefixes = kwargs.get('later_prefixes')
        if prefixes is not None:
            if first_prefixes is not None or later_prefixes is not None:
                raise TypeError(
                    'do not pass first_prefixes or later_prefixes '
                    'if prefixes is passed')
            first_prefixes = later_prefixes = prefixes
        prefix = kwargs.get('prefix')
        first_prefix = kwargs.get('first_prefix')
        later_prefix = kwargs.get('later_prefix')
        if prefix is not None:
            if first_prefix is not None or later_prefix is not None:
                raise TypeError(
                    'do not pass first_prefix or later_prefix with prefix')
            first_prefix = later_prefix = prefix
        if first_prefix is not None:
            if first_prefixes is not None:
                raise TypeError(
                    'do not pass both first_prefix and first_prefixes')
            first_prefixes = (first_prefix,)
        if later_prefix is not None:
            if later_prefixes is not None:
                raise TypeError(
                    'do not pass both later_prefix and later_prefixes')
            later_prefixes = (later_prefix,)
        if first_prefixes is not None:
            self.first_prefix.extend(first_prefixes)
        if later_prefixes is not None:
            self.later_prefix.extend(later_prefixes)
        try:
            for arg in args:
                # If we're at the start of the line, write our prefix.
                # There is a deficiency here: if neither our arg nor our
                # prefix affect _pos (both are escape sequences or empty)
                # we will write prefix more than once. This should not
                # matter.
                if not self._pos:
                    self._write_prefix(wrap)
                while callable(arg):
                    arg = arg(self)
                if arg is None:
                    continue
                if not isinstance(arg, str):
                    arg = str(arg)
                conversion_needed = self._encoding_conversion_needed(arg)
                while wrap and self._pos + len(arg) > self.width:
                    # We have to split.
                    maxlen = self.width - self._pos
                    space = arg.rfind(' ', 0, maxlen)
                    if space == -1:
                        # No space to split on.

                        # If we are on the first line we can simply go to
                        # the next (this helps if the "later" prefix is
                        # shorter and should not really matter if not).

                        # If we are on the second line and have already
                        # written something we can also go to the next
                        # line.
                        if self._in_first_line or self._wrote_something:
                            bit = ''
                        else:
                            # Forcibly split this as far to the right as
                            # possible.
                            bit = arg[:maxlen]
                            arg = arg[maxlen:]
                    else:
                        bit = arg[:space]
                        # Omit the space we split on.
                        arg = arg[space + 1:]
                    if conversion_needed:
                        bit = self._force_encoding(bit)
                    self.stream.write(bit)
                    self.stream.write(self._force_encoding('\n'))
                    self._pos = 0
                    self._in_first_line = False
                    self._wrote_something = False
                    self._write_prefix(wrap)

                # This fits.
                self._wrote_something = True
                self._pos += len(arg)
                if conversion_needed:
                    arg = self._force_encoding(arg)
                self.stream.write(arg)
            if autoline:
                self.stream.write(self._force_encoding('\n'))
                self._wrote_something = False
                self._pos = 0
                self._in_first_line = True
        except IOError as e:
            if e.errno == errno.EPIPE:
                raise StreamClosed(e)
            raise
        finally:
            if first_prefixes is not None:
                self.first_prefix = self.first_prefix[:-len(first_prefixes)]
            if later_prefixes is not None:
                self.later_prefix = self.later_prefix[:-len(later_prefixes)]

    def fg(self, color=None):
        """change fg color

        Compatibility method- no coloring escapes are returned from it.
        """
        return ''

    def bg(self, color=None):
        """change bg color

        Compatibility method- no coloring escapes are returned from it.
        """
        return ''

    def flush(self):
        self.stream.flush()






class TerminfoDisabled(Exception):
    """Raised if Terminfo is disabled."""


class _BogusTerminfo(ValueError):
    """Internal terminfo exception."""


class TerminfoUnsupported(Exception):
    """Raised if our terminal type is unsupported."""

    def __init__(self, term):
        self.term = term

    def __str__(self):
        return f'unsupported terminal type: {self.term!r}'


# This is necessary because the curses module is optional (and we
# should run on a very minimal python for bootstrapping).
try:
    import curses
except ImportError:
    TerminfoColor = None
else:
    class TerminfoColor:
        """Class encapsulating a specific terminfo entry for a color.

        This should not generally be invoked by hand, instead returned by
        the formatter itself.
        """

        __slots__ = ("mode", "color", "__weakref__")

        def __init__(self, mode, color):
            object.__setattr__(self, 'mode', mode)
            object.__setattr__(self, 'color', color)

        def __call__(self, formatter):
            if self.color is None:
                formatter._current_colors[self.mode] = None
                res = formatter._color_reset
                # slight abuse of boolean True/False and 1/0 equivalence
                other = formatter._current_colors[not self.mode]
                if other is not None:
                    res = res + other
            else:
                if self.mode == 0:
                    default = curses.COLOR_WHITE
                else:
                    default = curses.COLOR_BLACK
                color = formatter._colors.get(self.color, default)
                # The curses module currently segfaults if handed a
                # bogus template so check explicitly.
                template = formatter._set_color[self.mode]
                if template:
                    res = curses.tparm(template, color)
                else:
                    res = b''
                formatter._current_colors[self.mode] = res
            formatter.stream.write(res)

        def __setattr__(self, key, val):
            raise AttributeError("%s instances are immutable" %
                                 (self.__class__.__name__,))

    class TerminfoCode:
        """Encapsulates specific terminfo entry commands, reset for example.

        This should not generally be invoked by hand, instead returned by
        the formatter itself.
        """

        __slots__ = ("value", "__weakref__")

        def __init__(self, value):
            if value is None:
                raise _BogusTerminfo()
            object.__setattr__(self, 'value', value)

        def __setattr__(self, key, value):
            raise AttributeError("%s instances are immutable" %
                                 (self.__class__.__name__,))

    class TerminfoMode(TerminfoCode):

        __doc__ = TerminfoCode.__doc__
        __slots__ = ()

        def __call__(self, formatter):
            formatter._modes.add(self)
            formatter.stream.write(self.value)

    class TerminfoReset(TerminfoCode):

        __doc__ = TerminfoCode.__doc__
        __slots__ = ()

        def __call__(self, formatter):
            formatter._modes.clear()
            formatter.stream.write(self.value)

    class TerminfoFormatter(PlainTextFormatter):
        """Formatter writing to a tty, using terminfo to do colors."""

        _colors = dict(
            black=curses.COLOR_BLACK,
            red=curses.COLOR_RED,
            green=curses.COLOR_GREEN,
            yellow=curses.COLOR_YELLOW,
            blue=curses.COLOR_BLUE,
            magenta=curses.COLOR_MAGENTA,
            cyan=curses.COLOR_CYAN,
            white=curses.COLOR_WHITE,
        )

        def __init__(self, stream, term=None, encoding=None):
            """Initialize.

            :type stream: file-like object.
            :param stream: stream to output to, defaulting to :py:class:`sys.stdout`.
            :type term: string.
            :param term: terminal type, pulled from the environment if omitted.
            """
            super().__init__(stream, encoding=encoding)
            fd = stream.fileno()
            if term is None:
                if term := os.environ.get('TERM'):
                    try:
                        curses.setupterm(fd=fd, term=term)
                    except curses.error:
                        pass
                else:
                    raise TerminfoDisabled('no terminfo entries')
            else:
                # TODO maybe do something more useful than raising curses.error
                # if term is not in the terminfo db here?
                curses.setupterm(fd=fd, term=term)
            self._term = term
            self.width = curses.tigetnum('cols')
            try:
                self.reset = TerminfoReset(curses.tigetstr('sgr0'))
                self.bold = TerminfoMode(curses.tigetstr('bold'))
                self.underline = TerminfoMode(curses.tigetstr('smul'))
                self._color_reset = curses.tigetstr('op')
                self._set_color = (
                    curses.tigetstr('setaf'),
                    curses.tigetstr('setab'))
            except (_BogusTerminfo, curses.error) as e:
                raise TerminfoUnsupported(self._term) from e

            if not all(self._set_color):
                raise TerminfoDisabled(
                    'setting background/foreground colors is not supported')

            curses.tparm(self._set_color[0], curses.COLOR_WHITE)

            # [fg, bg]
            self._current_colors = [None, None]
            self._modes = set()
            self._pos = 0
            self._fg_cache = defaultdictkey(partial(TerminfoColor, 0))
            self._bg_cache = defaultdictkey(partial(TerminfoColor, 1))

        @steal_docs(Formatter)
        def fg(self, color=None):
            return self._fg_cache[color]

        @steal_docs(Formatter)
        def bg(self, color=None):
            return self._bg_cache[color]

        @steal_docs(Formatter)
        def write(self, *args, **kwargs):
            super().write(*args, **kwargs)
            try:
                if self._modes:
                    self.reset(self)
                if self._current_colors != [None, None]:
                    self._current_colors = [None, None]
                    self.stream.write(self._color_reset)
            except IOError as e:
                if e.errno == errno.EPIPE:
                    raise StreamClosed(e)
                raise

        @steal_docs(Formatter)
        def title(self, string):
            # I want to use curses.tigetflag('hs') here but at least
            # the screen-s entry defines a tsl and fsl string but does
            # not set the hs flag. So just check for the ability to
            # jump to and out of the status line, without checking if
            # the status line we're using exists.
            tsl = curses.tigetstr('tsl')
            fsl = curses.tigetstr('fsl')
            if tsl and fsl:
                self.stream.write(
                    tsl + string.encode(self.encoding, 'replace') + fsl)
                self.stream.flush()


class ObserverFormatter:

    def __init__(self, real_formatter):
        self._formatter = real_formatter

    def write(self, *args):
        self._formatter.write(autoline=False, *args)

    __getattr__ = GetAttrProxy("_formatter")


fileno_excepts = (AttributeError, io.UnsupportedOperation)


def get_formatter(stream, force_color=False):
    """TerminfoFormatter if the stream is a tty, else PlainTextFormatter."""
    if TerminfoColor is None:
        return PlainTextFormatter(stream)
    try:
        fd = stream.fileno()
    except fileno_excepts:
        pass
    else:
        # We do this instead of stream.isatty() because TerminfoFormatter
        # needs an fd to pass to curses, not just a filelike talking to a tty.
        if os.isatty(fd) or force_color:
            try:
                term = 'ansi' if force_color else None
                return TerminfoFormatter(stream, term=term)
            except (curses.error, TerminfoDisabled, TerminfoUnsupported):
                # This happens if TERM is unset and possibly in more cases.
                # Just fall back to the PlainTextFormatter.
                pass
    return PlainTextFormatter(stream)


def decorate_forced_wrapping(setting=True):
    """Decorator to force a specific line wrapping state for the duration of invocation."""
    def wrapped_func(func):
        def f(out, *args, **kwds):
            oldwrap = out.wrap
            out.wrap = setting
            try:
                return func(out, *args, **kwds)
            finally:
                out.wrap = oldwrap
        return f
    return wrapped_func
