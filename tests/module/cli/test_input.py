import errno
from functools import partial
from unittest import mock

import pytest

from snakeoil.cli.input import userquery, NoChoice
from snakeoil.test.argparse_helpers import FakeStreamFormatter


@pytest.fixture
def mocked_input():
    with mock.patch('builtins.input') as mocked_input:
        yield mocked_input


class TestUserQuery:

    @pytest.fixture(autouse=True)
    def __setup(self):
        self.out = FakeStreamFormatter()
        self.err = FakeStreamFormatter()
        self.query = partial(userquery, out=self.out, err=self.err)

    def test_default_answer(self, mocked_input):
        mocked_input.return_value = ''
        assert self.query('foo') == True

    def test_tuple_prompt(self, mocked_input):
        mocked_input.return_value = ''
        prompt = 'perhaps a tuple'
        assert self.query(tuple(prompt.split())) == True
        output = ''.join(prompt.split())
        assert self.out.get_text_stream().strip().split('\n')[0][:len(output)] == output

    def test_no_default_answer(self, mocked_input):
        responses = {
            'a': ('z', 'Yes'),
            'b': ('y', 'No'),
        }
        # no default answer returns None for empty input
        mocked_input.return_value = ''
        assert self.query('foo', responses=responses) == None
        mocked_input.return_value = 'a'
        assert self.query('foo', responses=responses) == 'z'
        mocked_input.return_value = 'b'
        assert self.query('foo', responses=responses) == 'y'

    def test_ambiguous_input(self, mocked_input):
        responses = {
            'a': ('z', 'Yes'),
            'A': ('y', 'No'),
        }
        mocked_input.return_value = 'a'
        with pytest.raises(NoChoice):
            self.query('foo', responses=responses)
        error_output = self.err.get_text_stream().strip().split('\n')[1]
        expected = 'Response %r is ambiguous (%s)' % (
            mocked_input.return_value, ', '.join(sorted(responses.keys())))
        assert error_output == expected

    def test_default_correct_input(self, mocked_input):
        for input, output in (('no', False),
                            ('No', False),
                            ('yes', True),
                            ('Yes', True)):
            mocked_input.return_value = input
            assert self.query('foo') == output

    def test_default_answer_no_matches(self, mocked_input):
        mocked_input.return_value = ''
        with pytest.raises(ValueError):
            self.query('foo', default_answer='foo')
        assert self.out.stream == []

    def test_custom_default_answer(self, mocked_input):
        mocked_input.return_value = ''
        assert self.query('foo', default_answer=False) == False

    def test_eof_nochoice(self, mocked_input):
        # user hits ctrl-d
        mocked_input.side_effect = EOFError
        with pytest.raises(NoChoice):
            self.query('foo')
        output = self.out.get_text_stream().strip().split('\n')[1]
        expected = 'Not answerable: EOF on STDIN'
        assert output == expected

    def test_stdin_closed_nochoice(self, mocked_input):
        mocked_input.side_effect = IOError(errno.EBADF, '')
        with pytest.raises(NoChoice):
            self.query('foo')
        output = self.out.get_text_stream().strip().split('\n')[1]
        expected = 'Not answerable: STDIN is either closed, or not readable'
        assert output == expected

    def test_unhandled_ioerror(self, mocked_input):
        mocked_input.side_effect = IOError(errno.ENODEV, '')
        with pytest.raises(IOError):
            self.query('foo')

    def test_bad_choice_limit(self, mocked_input):
        # user hits enters a bad choice 3 times in a row
        mocked_input.return_value = 'bad'
        with pytest.raises(NoChoice):
            self.query('foo')
        assert mocked_input.call_count == 3
        output = self.err.get_text_stream().strip().split('\n')[1]
        expected = "Sorry, response %r not understood." % (mocked_input.return_value,)
        assert output == expected

    def test_custom_choice_limit(self, mocked_input):
        # user hits enters a bad choice 5 times in a row
        mocked_input.return_value = 'haha'
        with pytest.raises(NoChoice):
            self.query('foo', limit=5)
        assert mocked_input.call_count == 5
        output = self.err.get_text_stream().strip().split('\n')[1]
        expected = "Sorry, response %r not understood." % (mocked_input.return_value,)
        assert output == expected
