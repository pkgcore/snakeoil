from io import StringIO

import pytest
from snakeoil.bash import (BashParseError, iter_read_bash, read_bash,
                           read_bash_dict, read_dict)


class TestBashCommentStripping:

    def test_iter_read_bash(self):
        output = iter_read_bash(StringIO(
            '\n'
            '# hi I am a comment\n'
            'I am not \n'
            ' asdf # inline comment\n'))
        assert list(output) == ['I am not', 'asdf']

        output = iter_read_bash(StringIO(
            'inline # comment '), allow_inline_comments=False)
        assert list(output) == ['inline # comment']

    def test_iter_read_bash_line_cont(self):
        output = iter_read_bash(StringIO(
            '\n'
            '# hi I am a comment\\\n'
            'I am not \\\n'
            'a comment \n'
            ' asdf # inline comment\\\n'),
            allow_line_cont=True)
        assert list(output) == ['I am not a comment', 'asdf']

        # continuation into inline comment
        output = iter_read_bash(StringIO(
            '\n'
            '# hi I am a comment\n'
            'I am \\\n'
            'not a \\\n'
            'comment # inline comment\n'),
            allow_line_cont=True)
        assert list(output) == ['I am not a comment']

        # ends with continuation
        output = iter_read_bash(StringIO(
            '\n'
            '# hi I am a comment\n'
            'I am \\\n'
            '\\\n'
            'not a \\\n'
            'comment\\\n'
            '\\\n'),
            allow_line_cont=True)
        assert list(output) == ['I am not a comment']

        # embedded comment prefix via continued lines
        output = iter_read_bash(StringIO(
            '\\\n'
            '# comment\\\n'
            ' not a comment\n'
            '\\\n'
            ' # inner comment\n'
            'also not\\\n'
            '#\\\n'
            'a comment\n'),
            allow_line_cont=True)
        assert list(output) == ['not a comment', 'also not#a comment']

        # Line continuations have to end with \<newline> without any backslash
        # before the pattern.
        output = iter_read_bash(StringIO(
            'I am \\ \n'
            'not a comment'),
            allow_line_cont=True)
        assert list(output) == ['I am \\', 'not a comment']
        output = iter_read_bash(StringIO(
            '\\\n'
            'I am \\\\\n'
            'not a comment'),
            allow_line_cont=True)
        assert list(output) == ['I am \\\\', 'not a comment']

    def test_read_bash(self):
        output = read_bash(StringIO(
            '\n'
            '# hi I am a comment\n'
            'I am not\n'))
        assert output == ['I am not']


class TestReadDictConfig:

    def test_read_dict(self):
        bash_dict = read_dict(StringIO(
            '\n'
            '# hi I am a comment\n'
            'foo1=bar\n'
            'foo2="bar"\n'
            'foo3=\'bar"\n'))
        assert bash_dict == {
            'foo1': 'bar',
            'foo2': 'bar',
            'foo3': '\'bar"',
            }
        assert read_dict(['foo=bar'], source_isiter=True) == {'foo': 'bar'}

        with pytest.raises(BashParseError):
            read_dict(['invalid'], source_isiter=True)

        bash_dict = read_dict(StringIO("foo bar\nfoo2  bar\nfoo3\tbar\n"), splitter=None)
        assert bash_dict == dict.fromkeys(('foo', 'foo2', 'foo3'), 'bar')
        bash_dict = read_dict(['foo = blah', 'foo2= blah ', 'foo3=blah'], strip=True)
        assert bash_dict == dict.fromkeys(('foo', 'foo2', 'foo3'), 'blah')


class TestReadBashDict:

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        self.valid_file = tmp_path / "valid"
        self.valid_file.write_text(
            '# hi I am a comment\n'
            'foo1=bar\n'
            "foo2='bar'\n"
            'foo3="bar"\n'
            'foo4=-/:j4\n'
            'foo5=\n'
            'export foo6="bar"\n'
        )
        self.sourcing_file = tmp_path / "sourcing"
        self.sourcing_file.write_text(f'source "{self.valid_file}"\n')
        self.sourcing_file2 = tmp_path / "sourcing2"
        self.sourcing_file2.write_text(f'source "{self.valid_file}"\n')
        self.advanced_file = tmp_path / "advanced"
        self.advanced_file.write_text(
            'one1=1\n'
            'one_=$one1\n'
            'two1=2\n'
            'two_=${two1}\n'
        )
        self.env_file = tmp_path / "env"
        self.env_file.write_text('imported=${external}\n')
        self.escaped_file = tmp_path / "escaped"
        self.escaped_file.write_text(
            'end=bye\n'
            'quoteddollar="\\${dollar}"\n'
            'quotedexpansion="\\${${end}}"\n'
        )
        self.unclosed_file = tmp_path / "unclosed"
        self.unclosed_file.write_text('foo="bar')

    def invoke_and_close(self, handle, *args, **kwds):
        try:
            return read_bash_dict(handle, *args, **kwds)
        finally:
            if hasattr(handle, 'close'):
                handle.close()

    def test_read_bash_dict(self):
        # TODO this is not even close to complete
        bash_dict = self.invoke_and_close(str(self.valid_file))
        d = {
            'foo1': 'bar',
            'foo2': 'bar',
            'foo3': 'bar',
            'foo4': '-/:j4',
            'foo5': '',
            'foo6': 'bar',
        }
        assert bash_dict == d

        with pytest.raises(BashParseError):
            self.invoke_and_close(StringIO("a=b\ny='"))

    def test_var_read(self):
        assert self.invoke_and_close(StringIO("x=y@a\n")) == {'x': 'y@a'}
        assert self.invoke_and_close(StringIO("x=y~a\n")) == {'x': 'y~a'}
        assert self.invoke_and_close(StringIO("x=y^a\n")) == {'x': 'y^a'}
        assert self.invoke_and_close(StringIO('x="\nasdf\nfdsa"')) == {'x': '\nasdf\nfdsa'}

    def test_empty_assign(self):
        self.valid_file.write_text("foo=\ndar=blah\n")
        assert self.invoke_and_close(str(self.valid_file)) == {'foo': '', 'dar': 'blah'}
        self.valid_file.write_text("foo=\ndar=\n")
        assert self.invoke_and_close(str(self.valid_file)) == {'foo': '', 'dar': ''}
        self.valid_file.write_text("foo=blah\ndar=\n")
        assert self.invoke_and_close(str(self.valid_file)) == {'foo': 'blah', 'dar': ''}

    def test_quoting(self):
        assert self.invoke_and_close(StringIO("x='y \\\na'")) == {'x': 'y \\\na'}
        assert self.invoke_and_close(StringIO("x='y'a\n")) == {'x': "ya"}
        assert self.invoke_and_close(StringIO('x="y \\\nasdf"')) == {'x': 'y asdf'}

    def test_eof_without_newline(self):
        assert self.invoke_and_close(StringIO("x=y")) == {'x': 'y'}
        assert self.invoke_and_close(StringIO("x='y'a")) == {'x': 'ya'}

    def test_sourcing(self):
        output = self.invoke_and_close(str(self.sourcing_file), sourcing_command='source')
        expected = {'foo1': 'bar', 'foo2': 'bar', 'foo3': 'bar', 'foo4': '-/:j4', 'foo5': '', 'foo6': 'bar'}
        assert output == expected
        output = self.invoke_and_close(str(self.sourcing_file2), sourcing_command='source')
        expected = {'foo1': 'bar', 'foo2': 'bar', 'foo3': 'bar', 'foo4': '-/:j4', 'foo5': '', 'foo6': 'bar'}
        assert output == expected

    def test_read_advanced(self):
        output = self.invoke_and_close(str(self.advanced_file))
        expected = {
            'one1': '1',
            'one_': '1',
            'two1': '2',
            'two_': '2',
        }
        assert output == expected

    def test_env(self):
        assert self.invoke_and_close(str(self.env_file)) == {'imported': ''}
        env = {'external': 'imported foo'}
        env_backup = env.copy()
        assert self.invoke_and_close(str(self.env_file), env) == {'imported': 'imported foo'}
        assert env_backup == env

    def test_escaping(self):
        output = self.invoke_and_close(str(self.escaped_file))
        expected = {
            'end': 'bye',
            'quoteddollar': '${dollar}',
            'quotedexpansion': '${bye}',
        }
        assert output == expected

    def test_unclosed(self):
        with pytest.raises(BashParseError):
            self.invoke_and_close(str(self.unclosed_file))

    def test_wordchards(self):
        assert self.invoke_and_close(StringIO("x=-*")) == {"x": "-*"}
