# Copyright: 2007 Brian Harring <ferringb@gmail.com>
# Copyright: 2006 Marien Zwart <marienz@gentoo.org>
# License: GPL2

# TODO:
# for PlainTextFormatter, wouldn't be a bad idea to add a method for testing
# that compares native vs cpy behaviour behind the scenes for each test.
# aside from that, tests need heavy expansion

import StringIO
import tempfile

from snakeoil.test import TestCase

from snakeoil import formatters


class native_PlainTextFormatterTest(TestCase):

    kls = staticmethod(formatters.native_PlainTextFormatter)

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
            stream = StringIO.StringIO()
            formatter = self.kls(stream, encoding='ascii')
            formatter.width = 20
            formatter.write(autoline=False, wrap=True, *inputs)
            self.assertEqual(output, stream.getvalue())

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
            stream = StringIO.StringIO()
            formatter = self.kls(stream, encoding='ascii')
            formatter.width = 20
            formatter.write(autoline=False, wrap=True, first_prefix='foon:',
                            *inputs)
            self.assertEqual(output, stream.getvalue())

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
            stream = StringIO.StringIO()
            formatter = self.kls(stream, encoding='ascii')
            formatter.width = 20
            formatter.later_prefix = ['foon:']
            formatter.write(wrap=True, autoline=False, *inputs)
            self.assertEqual(output, stream.getvalue())

    def test_complex(self):
        stream = StringIO.StringIO()
        formatter = self.kls(stream, encoding='ascii')
        formatter.width = 9
        formatter.first_prefix = ['foo', None, ' d']
        formatter.later_prefix = ['dorkey']
        formatter.write("dar bl", wrap=True, autoline=False)
        self.assertEqual("foo ddar\ndorkeybl", stream.getvalue())
        formatter.write(" "*formatter.width, wrap=True, autoline=True)
        formatter.stream = stream = StringIO.StringIO()
        formatter.write("dar", " b", wrap=True, autoline=False)
        self.assertEqual("foo ddar\ndorkeyb", stream.getvalue())
        output = \
"""     rdepends: >=dev-lang/python-2.3 >=sys-apps/sed-4.0.5
                       dev-python/python-fchksum
"""
        stream = StringIO.StringIO()
        formatter = self.kls(stream, encoding='ascii',
            width=80)
        formatter.wrap = True
        self.assertEqual(formatter.autoline, True)
        self.assertEqual(formatter.width, 80)
        formatter.later_prefix = ['                       ']
        formatter.write("     rdepends: >=dev-lang/python-2.3 "
            ">=sys-apps/sed-4.0.5 dev-python/python-fchksum")
        self.assertLen(formatter.first_prefix, 0)
        self.assertLen(formatter.later_prefix, 1)
        self.assertEqual(output, stream.getvalue())
        formatter.write()
        formatter.stream = stream = StringIO.StringIO()
        # push it right up to the limit.
        formatter.width = 82
        formatter.write("     rdepends: >=dev-lang/python-2.3 "
            ">=sys-apps/sed-4.0.5 dev-python/python-fchksum")
        self.assertEqual(output, stream.getvalue())

        formatter.first_prefix = []
        formatter.later_prefix = ['                  ']
        formatter.width = 28
        formatter.autoline = False
        formatter.wrap = True
        formatter.stream = stream = StringIO.StringIO()
        input = ("     description: ","The Portage")
        formatter.write(*input)
        output = ''.join(input).rsplit(" ", 1)
        output[1] = '                  %s' % output[1]
        self.assertEqual(output, stream.getvalue().split("\n"))


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
            stream = StringIO.StringIO()
            formatter = self.kls(stream, encoding='ascii')
            formatter.width = 10
            for input in inputs:
                formatter.write(wrap=True, later_prefix='foon', *input)
            self.assertEqual(output, stream.getvalue())


class cpy_PlainTextFormatterTest(native_PlainTextFormatterTest):
    kls = staticmethod(formatters.PlainTextFormatter)
    if formatters.native_PlainTextFormatter is formatters.PlainTextFormatter:
        skip = "cpy extension isn't available"


class TerminfoFormatterTest(TestCase):

    def _test_stream(self, stream, formatter, *data):
        for inputs, outputs in data:
            stream.seek(0)
            stream.truncate()
            formatter.write(*inputs)
            stream.seek(0)
            self.assertEqual(''.join(outputs), stream.read())

    def test_terminfo(self):
        esc = '\x1b['
        stream = tempfile.TemporaryFile()
        f = formatters.TerminfoFormatter(stream, 'ansi', True, 'ascii')
        f.autoline = False
        self._test_stream(
            stream, f,
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
            )
        f.autoline = True
        self._test_stream(
            stream, f, (('lala',), ('lala', '\n')))


