# Copyright: 2007 Brian Harring <ferringb@gmail.com>
# Copyright: 2006 Marien Zwart <marienz@gentoo.org>
# License: BSD/GPL2

# TODO:
# for PlainTextFormatter, wouldn't be a bad idea to add a method for testing
# that compares native vs cpy behaviour behind the scenes for each test.
# aside from that, tests need heavy expansion

import curses
import os
import pty
from tempfile import TemporaryFile

from snakeoil import formatters, compatibility
from snakeoil.test import SkipTest, TestCase, mk_cpy_loadable_testcase, protect_process

if compatibility.is_py3k:
    from io import BytesIO as StringIO
else:
    from StringIO import StringIO

# protect against python issue 7567 for the curses module.
issue7567 = protect_process

class native_PlainTextFormatterTest(TestCase):

    kls = staticmethod(formatters.native_PlainTextFormatter)

    def assertStreamEqual(self, output, stream):
        self.assertEqual(compatibility.force_bytes(output), stream.getvalue())

    def test_basics(self):
        # As many sporks as fit in 20 chars.
        sporks = ' '.join(3 * ('spork',))
        for inputs, output in [
                ((u'\N{SNOWMAN}',), '?'),
                ((7 * 'spork ',), '%s\n%s\n%s' % (sporks, sporks, 'spork ')),
                (7 * ('spork ',), '%s \n%s \n%s' % (sporks, sporks, 'spork ')),
                ((30 * 'a'), 20 * 'a' + '\n' + 10 * 'a'),
                (30 * ('a',), 20 * 'a' + '\n' + 10 * 'a'),
            ]:
            stream = StringIO()
            formatter = self.kls(stream, encoding='ascii')
            formatter.width = 20
            formatter.write(autoline=False, wrap=True, *inputs)
            self.assertStreamEqual(output, stream)

    def test_first_prefix(self):
        # As many sporks as fit in 20 chars.
        for inputs, output in [
                ((u'\N{SNOWMAN}',), 'foon:?'),
                ((7 * 'spork ',),
                 'foon:spork spork\n'
                 'spork spork spork\n'
                 'spork spork '),
                (7 * ('spork ',),
                 'foon:spork spork \n'
                 'spork spork spork \n'
                 'spork spork '),
                ((30 * 'a'), 'foon:' + 15 * 'a' + '\n' + 15 * 'a'),
                (30 * ('a',), 'foon:' + 15 * 'a' + '\n' + 15 * 'a'),
            ]:
            stream = StringIO()
            formatter = self.kls(stream, encoding='ascii')
            formatter.width = 20
            formatter.write(autoline=False, wrap=True, first_prefix='foon:',
                            *inputs)
            self.assertStreamEqual(output, stream)

    def test_later_prefix(self):
        for inputs, output in [
                ((u'\N{SNOWMAN}',), '?'),
                ((7 * 'spork ',),
                 'spork spork spork\n'
                 'foon:spork spork\n'
                 'foon:spork spork '),
                (7 * ('spork ',),
                 'spork spork spork \n'
                 'foon:spork spork \n'
                 'foon:spork spork '),
                ((30 * 'a'), 20 * 'a' + '\n' + 'foon:' + 10 * 'a'),
                (30 * ('a',), 20 * 'a' + '\n' + 'foon:' + 10 * 'a'),
            ]:
            stream = StringIO()
            formatter = self.kls(stream, encoding='ascii')
            formatter.width = 20
            formatter.later_prefix = ['foon:']
            formatter.write(wrap=True, autoline=False, *inputs)
            self.assertStreamEqual(output, stream)

    def test_complex(self):
        stream = StringIO()
        formatter = self.kls(stream, encoding='ascii')
        formatter.width = 9
        formatter.first_prefix = ['foo', None, ' d']
        formatter.later_prefix = ['dorkey']
        formatter.write("dar bl", wrap=True, autoline=False)
        self.assertStreamEqual("foo ddar\ndorkeybl", stream)
        formatter.write(" "*formatter.width, wrap=True, autoline=True)
        formatter.stream = stream = StringIO()
        formatter.write("dar", " b", wrap=True, autoline=False)
        self.assertStreamEqual("foo ddar\ndorkeyb", stream)
        output = \
"""     rdepends: >=dev-lang/python-2.3 >=sys-apps/sed-4.0.5
                       dev-python/python-fchksum
"""
        stream = StringIO()
        formatter = self.kls(stream, encoding='ascii', width=80)
        formatter.wrap = True
        self.assertEqual(formatter.autoline, True)
        self.assertEqual(formatter.width, 80)
        formatter.later_prefix = ['                       ']
        formatter.write("     rdepends: >=dev-lang/python-2.3 "
                        ">=sys-apps/sed-4.0.5 dev-python/python-fchksum")
        self.assertLen(formatter.first_prefix, 0)
        self.assertLen(formatter.later_prefix, 1)
        self.assertStreamEqual(output, stream)
        formatter.write()
        formatter.stream = stream = StringIO()
        # push it right up to the limit.
        formatter.width = 82
        formatter.write("     rdepends: >=dev-lang/python-2.3 "
                        ">=sys-apps/sed-4.0.5 dev-python/python-fchksum")
        self.assertStreamEqual(output, stream)

        formatter.first_prefix = []
        formatter.later_prefix = ['                  ']
        formatter.width = 28
        formatter.autoline = False
        formatter.wrap = True
        formatter.stream = stream = StringIO()
        input = ("     description: ", "The Portage")
        formatter.write(*input)
        output = ''.join(input).rsplit(" ", 1)
        output[1] = '                  %s' % output[1]
        self.assertStreamEqual('\n'.join(output), stream)


    def test_wrap_autoline(self):
        for inputs, output in [
                ((3 * ('spork',)), 'spork\nspork\nspork\n'),
                (3 * (('spork',),), 'spork\nspork\nspork\n'),
                (((3 * 'spork',),),
                 '\n'
                 'foonsporks\n'
                 'foonporksp\n'
                 'foonork\n'),
                ((('fo',), (2 * 'spork',),), 'fo\nsporkspork\n'),
                ((('fo',), (3 * 'spork',),),
                 'fo\n'
                 '\n'
                 'foonsporks\n'
                 'foonporksp\n'
                 'foonork\n'),
            ]:
            stream = StringIO()
            formatter = self.kls(stream, encoding='ascii')
            formatter.width = 10
            for input in inputs:
                formatter.write(wrap=True, later_prefix='foon', *input)
            self.assertStreamEqual(output, stream)


class cpy_PlainTextFormatterTest(native_PlainTextFormatterTest):
    kls = staticmethod(formatters.PlainTextFormatter)
    if formatters.native_PlainTextFormatter is formatters.PlainTextFormatter:
        skip = "cpy extension isn't available"


class TerminfoFormatterTest(TestCase):

    def _test_stream(self, stream, formatter, inputs, output):
        stream.seek(0)
        stream.truncate()
        formatter.write(*inputs)
        stream.seek(0)
        result = stream.read()
        self.assertEqual(compatibility.force_bytes(''.join(output)), result,
                         msg="given(%r), expected(%r), got(%r)" %
                         (inputs, ''.join(output), result))

    @issue7567
    def test_terminfo(self):
        esc = '\x1b['
        stream = TemporaryFile()
        f = formatters.TerminfoFormatter(stream, 'ansi', True, 'ascii')
        f.autoline = False
        for inputs, output in (
                ((f.bold, 'bold'), (esc, '1m', 'bold', esc, '0;10m')),
                ((f.underline, 'underline'),
                 (esc, '4m', 'underline', esc, '0;10m')),
                ((f.fg('red'), 'red'), (esc, '31m', 'red', esc, '39;49m')),
                ((f.fg('red'), 'red', f.bold, 'boldred', f.fg(), 'bold',
                  f.reset, 'done'),
                 (esc, '31m', 'red', esc, '1m', 'boldred', esc, '39;49m', 'bold',
                  esc, '0;10m', 'done')),
                ((42,), ('42',)),
                ((u'\N{SNOWMAN}',), ('?',))
            ):
            self._test_stream(stream, f, inputs, output)
        f.autoline = True
        self._test_stream(
            stream, f, ('lala',), ('lala', '\n'))

    def test_terminfo_hates_term(self):
        stream = TemporaryFile()
        self.assertRaises(
            formatters.TerminfoHatesOurTerminal,
            formatters.TerminfoFormatter, stream, term='dumb')

    @issue7567
    def test_title(self):
        stream = TemporaryFile()
        try:
            f = formatters.TerminfoFormatter(stream, 'xterm+sl', True, 'ascii')
        except curses.error:
            raise SkipTest("xterm+sl not in terminfo db")
        f.title('TITLE')
        stream.seek(0)
        self.assertEqual(b'\x1b]0;TITLE\x07', stream.read())


def _with_term(term, func, *args, **kwargs):
    orig_term = os.environ.get('TERM')
    try:
        os.environ['TERM'] = term
        return func(*args, **kwargs)
    finally:
        if orig_term is None:
            del os.environ['TERM']
        else:
            os.environ['TERM'] = orig_term

# XXX ripped from pkgcore's test_commandline
def _get_pty_pair(encoding='ascii'):
    master_fd, slave_fd = pty.openpty()
    master = os.fdopen(master_fd, 'rb', 0)
    out = os.fdopen(slave_fd, 'wb', 0)
    return master, out


class GetFormatterTest(TestCase):

    @issue7567
    def test_dumb_terminal(self):
        master, _out = _get_pty_pair()
        formatter = _with_term('dumb', formatters.get_formatter, master)
        self.failUnless(isinstance(formatter, formatters.PlainTextFormatter))

    @issue7567
    def test_vt100_terminal(self):
        formatter = _with_term('vt100', formatters.get_formatter, master)
        self.failUnless(isinstance(formatter, formatters.PlainTextFormatter))

    @issue7567
    def test_smart_terminal(self):
        master, _out = _get_pty_pair()
        formatter = _with_term('xterm', formatters.get_formatter, master)
        self.failUnless(isinstance(formatter, formatters.TerminfoFormatter))

    @issue7567
    def test_not_a_tty(self):
        stream = TemporaryFile()
        formatter = _with_term('xterm', formatters.get_formatter, stream)
        self.failUnless(isinstance(formatter, formatters.PlainTextFormatter))

    @issue7567
    def test_no_fd(self):
        stream = StringIO()
        formatter = _with_term('xterm', formatters.get_formatter, stream)
        self.failUnless(isinstance(formatter, formatters.PlainTextFormatter))


cpy_loaded_Test = mk_cpy_loadable_testcase(
    "snakeoil._formatters", "snakeoil.formatters", "StreamClosed",
    "StreamClosed")
