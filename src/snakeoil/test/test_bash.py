# Copyright: 2010-2011 Brian Harring <ferringb@gmail.com>
# Copyright: 2005 Marien Zwart <marienz@gentoo.org>
# License: BSD/GPL2

import os
from StringIO import StringIO

from snakeoil.bash import (
    iter_read_bash, read_bash, read_dict, read_bash_dict, BashParseError)
from snakeoil.test.mixins import mk_named_tempfile
from snakeoil.test import TestCase


class TestBashCommentStripping(TestCase):

    def test_iter_read_bash(self):
        self.assertEqual(
            list(iter_read_bash(StringIO(
                '\n'
                '# hi I am a comment\n'
                'I am not \n'
                ' asdf # inline comment\n'))),
            ['I am not', 'asdf'])
        self.assertEqual(
            list(iter_read_bash(StringIO(
                'inline # comment '), allow_inline_comments=False)),
            ['inline # comment'])

    def test_iter_read_bash_line_cont(self):
        self.assertEqual(
            list(iter_read_bash(StringIO(
                '\n'
                '# hi I am a comment\\\n'
                'I am not \\\n'
                'a comment \n'
                ' asdf # inline comment\\\n'),
                allow_line_cont=True)),
            ['I am not a comment', 'asdf'])

        # continuation into inline comment
        self.assertEqual(
            list(iter_read_bash(StringIO(
                '\n'
                '# hi I am a comment\n'
                'I am \\\n'
                'not a \\\n'
                'comment # inline comment\n'),
                allow_line_cont=True)),
            ['I am not a comment'])

        # ends with continuation
        self.assertEqual(
            list(iter_read_bash(StringIO(
                '\n'
                '# hi I am a comment\n'
                'I am \\\n'
                '\\\n'
                'not a \\\n'
                'comment\\\n'
                '\\\n'),
                allow_line_cont=True)),
            ['I am not a comment'])

        # embedded comment prefix via continued lines
        self.assertEqual(
            list(iter_read_bash(StringIO(
                '\\\n'
                '# comment\\\n'
                ' not a comment\n'
                '\\\n'
                ' # inner comment\n'
                'also not\\\n'
                '#\\\n'
                'a comment\n'),
                allow_line_cont=True)),
            ['not a comment', 'also not#a comment'])

        # Line continuations have to end with \<newline> without any backslash
        # before the pattern.
        self.assertEqual(
            list(iter_read_bash(StringIO(
                'I am \\ \n'
                'not a comment'),
                allow_line_cont=True)),
            ['I am \\', 'not a comment'])
        self.assertEqual(
            list(iter_read_bash(StringIO(
                '\\\n'
                'I am \\\\\n'
                'not a comment'),
                allow_line_cont=True)),
            ['I am \\\\', 'not a comment'])

    def test_read_bash(self):
        self.assertEqual(
            read_bash(StringIO(
                '\n'
                '# hi I am a comment\n'
                'I am not\n')),
            ['I am not'])


class TestReadDictConfig(TestCase):

    def test_read_dict(self):
        self.assertEqual(
            read_dict(StringIO(
                '\n'
                '# hi I am a comment\n'
                'foo1=bar\n'
                'foo2="bar"\n'
                'foo3=\'bar"\n')),
            {'foo1': 'bar',
             'foo2': 'bar',
             'foo3': '\'bar"',})
        self.assertEqual(
            read_dict(['foo=bar'], source_isiter=True), {'foo': 'bar'})
        self.assertRaises(
            BashParseError, read_dict, ['invalid'], source_isiter=True)
        self.assertEqual(
            read_dict(StringIO("foo bar\nfoo2  bar\nfoo3\tbar\n"),
                      splitter=None),
            {}.fromkeys(('foo', 'foo2', 'foo3'), 'bar'))
        self.assertEqual(
            read_dict(['foo = blah', 'foo2= blah ', 'foo3=blah'], strip=True),
            {}.fromkeys(('foo', 'foo2', 'foo3'), 'blah'))


class ReadBashDictTest(TestCase):

    def setUp(self):
        self.valid_file = mk_named_tempfile()
        self.valid_file.write(
            '# hi I am a comment\n'
            'foo1=bar\n'
            "foo2='bar'\n"
            'foo3="bar"\n'
            'foo4=-/:j4\n'
            'foo5=\n')
        self.valid_file.flush()
        self.sourcing_file = mk_named_tempfile()
        self.sourcing_file.write('source "%s"\n' % self.valid_file.name)
        self.sourcing_file.flush()
        self.sourcing_file2 = mk_named_tempfile()
        self.sourcing_file2.write('source "%s"\n' % os.path.basename(self.valid_file.name))
        self.sourcing_file2.flush()
        self.advanced_file = mk_named_tempfile()
        self.advanced_file.write(
            'one1=1\n'
            'one_=$one1\n'
            'two1=2\n'
            'two_=${two1}\n'
            )
        self.advanced_file.flush()
        self.env_file = mk_named_tempfile()
        self.env_file.write(
            'imported=${external}\n'
            )
        self.env_file.flush()
        self.escaped_file = mk_named_tempfile()
        self.escaped_file.write(
            'end=bye\n'
            'quoteddollar="\\${dollar}"\n'
            'quotedexpansion="\\${${end}}"\n'
            )
        self.escaped_file.flush()
        self.unclosed_file = mk_named_tempfile()
        self.unclosed_file.write('foo="bar')
        self.unclosed_file.flush()

    def tearDown(self):
        for x in ("valid", "sourcing", "advanced", "env", "escaped", "unclosed"):
            x = getattr(self, '%s_file' % x, None)
            if x is not None:
                x.close()

    def invoke_and_close(self, handle, *args, **kwds):
        try:
            return read_bash_dict(handle, *args, **kwds)
        finally:
            if hasattr(handle, 'close'):
                handle.close()

    def test_read_bash_dict(self):
        # TODO this is not even close to complete
        self.assertEqual(
            self.invoke_and_close(self.valid_file.name),
            {'foo1': 'bar', 'foo2': 'bar', 'foo3': 'bar', 'foo4': '-/:j4',
             'foo5': ''})
        s = "a=b\ny='"
        self.assertRaises(BashParseError, self.invoke_and_close, StringIO(s))

    def test_var_read(self):
        self.assertEqual(self.invoke_and_close(StringIO("x=y@a\n")),
                         {'x': 'y@a'})
        self.assertEqual(self.invoke_and_close(StringIO("x=y~a\n")),
                         {'x': 'y~a'})
        self.assertEqual(self.invoke_and_close(StringIO("x=y^a\n")),
                         {'x': 'y^a'})
        self.assertEqual(self.invoke_and_close(StringIO('x="\nasdf\nfdsa"')),
                         {'x': '\nasdf\nfdsa'})

    def test_empty_assign(self):
        self.write_file(self.valid_file.name, 'w', "foo=\ndar=blah\n")
        self.assertEqual(self.invoke_and_close(self.valid_file.name),
                         {'foo': '', 'dar': 'blah'})
        self.write_file(self.valid_file.name, 'w', "foo=\ndar=\n")
        self.assertEqual(self.invoke_and_close(self.valid_file.name),
                         {'foo': '', 'dar': ''})
        self.write_file(self.valid_file.name, 'w', "foo=blah\ndar=\n")
        self.assertEqual(self.invoke_and_close(self.valid_file.name),
                         {'foo': 'blah', 'dar': ''})

    def test_quoting(self):
        self.assertEqual(self.invoke_and_close(StringIO("x='y \\\na'")),
                         {'x': 'y \\\na'})
        self.assertEqual(self.invoke_and_close(StringIO("x='y'a\n")),
                         {'x': "ya"})
        self.assertEqual(self.invoke_and_close(StringIO('x="y \\\nasdf"')),
                         {'x': 'y asdf'})

    def test_eof_without_newline(self):
        self.assertEqual(self.invoke_and_close(StringIO("x=y")), {'x': 'y'})
        self.assertEqual(self.invoke_and_close(StringIO("x='y'a")), {'x': 'ya'})

    def test_sourcing(self):
        self.assertEqual(
            self.invoke_and_close(self.sourcing_file.name, sourcing_command='source'),
            {'foo1': 'bar', 'foo2': 'bar', 'foo3': 'bar', 'foo4': '-/:j4',
             'foo5': ''})
        self.assertEqual(
            self.invoke_and_close(self.sourcing_file2.name, sourcing_command='source'),
            {'foo1': 'bar', 'foo2': 'bar', 'foo3': 'bar', 'foo4': '-/:j4',
             'foo5': ''})

    def test_read_advanced(self):
        self.assertEqual(
            self.invoke_and_close(self.advanced_file.name),
            {'one1': '1',
             'one_': '1',
             'two1': '2',
             'two_': '2',})

    def test_env(self):
        self.assertEqual(
            self.invoke_and_close(self.env_file.name),
            {'imported': ''})
        env = {'external': 'imported foo'}
        env_backup = env.copy()
        self.assertEqual(
            self.invoke_and_close(self.env_file.name, env),
            {'imported': 'imported foo'})
        self.assertEqual(env_backup, env)

    def test_escaping(self):
        self.assertEqual(
            self.invoke_and_close(self.escaped_file.name), {
                'end': 'bye',
                'quoteddollar': '${dollar}',
                'quotedexpansion': '${bye}',
                })

    def test_unclosed(self):
        self.assertRaises(BashParseError, self.invoke_and_close, self.unclosed_file.name)

    def test_wordchards(self):
        self.assertEqual(self.invoke_and_close(StringIO("x=-*")), {"x": "-*"})
