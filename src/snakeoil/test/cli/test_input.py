# Copyright: 2017 Tim Harder <radhermit@gmail.com>
# License: BSD/GPL2

import errno
from functools import partial
import unittest

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

from snakeoil import compatibility as compat
from snakeoil.cli import input as input_mod
from snakeoil.test.argparse_helpers import FakeStreamFormatter


class TestUserQuery(unittest.TestCase):

    def setUp(self):
        self.out = FakeStreamFormatter()
        self.err = FakeStreamFormatter()
        self.query = partial(input_mod.userquery, out=self.out, err=self.err)

    @patch.object(compat, 'input')
    def test_default_answer(self, fake_input):
        fake_input.return_value = ''
        self.assertEqual(self.query('foo'), True)

    @patch.object(compat, 'input')
    def test_tuple_prompt(self, fake_input):
        fake_input.return_value = ''
        prompt = 'perhaps a tuple'
        self.assertEqual(self.query(tuple(prompt.split())), True)
        output = ''.join(prompt.split())
        self.assertEqual(
            self.out.get_text_stream().strip().split('\n')[0][:len(output)],
            output)

    @patch.object(compat, 'input')
    def test_no_default_answer(self, fake_input):
        responses = {
            'a': ('z', 'Yes'),
            'b': ('y', 'No'),
        }
        # no default answer returns None for empty input
        fake_input.return_value = ''
        self.assertEqual(self.query('foo', responses=responses), None)
        fake_input.return_value = 'a'
        self.assertEqual(self.query('foo', responses=responses), 'z')
        fake_input.return_value = 'b'
        self.assertEqual(self.query('foo', responses=responses), 'y')

    @patch.object(compat, 'input')
    def test_ambiguous_input(self, fake_input):
        responses = {
            'a': ('z', 'Yes'),
            'A': ('y', 'No'),
        }
        fake_input.return_value = 'a'
        with self.assertRaises(input_mod.NoChoice):
            self.query('foo', responses=responses)
        self.assertEqual(
            self.err.get_text_stream().strip().split('\n')[1],
            'Response %r is ambiguous (%s)' % (
                fake_input.return_value, ', '.join(sorted(responses.iterkeys()))))

    @patch.object(compat, 'input')
    def test_default_correct_input(self, fake_input):
        for input, output in (('no', False),
                              ('No', False),
                              ('yes', True),
                              ('Yes', True)):
            fake_input.return_value = input
            self.assertEqual(self.query('foo'), output)

    @patch.object(compat, 'input')
    def test_default_answer_no_matches(self, fake_input):
        fake_input.return_value = ''
        with self.assertRaises(ValueError):
            self.query('foo', default_answer='foo')
        self.assertEqual(self.out.stream, [])

    @patch.object(compat, 'input')
    def test_custom_default_answer(self, fake_input):
        fake_input.return_value = ''
        self.assertEqual(self.query('foo', default_answer=False), False)

    @patch.object(compat, 'input')
    def test_eof_nochoice(self, fake_input):
        # user hits ctrl-d
        fake_input.side_effect = EOFError
        with self.assertRaises(input_mod.NoChoice):
            self.query('foo')
        self.assertEqual(
            self.out.get_text_stream().strip().split('\n')[1],
            'Not answerable: EOF on STDIN')

    @patch.object(compat, 'input')
    def test_stdin_closed_nochoice(self, fake_input):
        fake_input.side_effect = IOError(errno.EBADF, '')
        with self.assertRaises(input_mod.NoChoice):
            self.query('foo')
        self.assertEqual(
            self.out.get_text_stream().strip().split('\n')[1],
            'Not answerable: STDIN is either closed, or not readable')

    @patch.object(compat, 'input')
    def test_unhandled_ioerror(self, fake_input):
        fake_input.side_effect = IOError(errno.ENODEV, '')
        with self.assertRaises(IOError):
            self.query('foo')

    @patch.object(compat, 'input')
    def test_bad_choice_limit(self, fake_input):
        # user hits enters a bad choice 3 times in a row
        fake_input.return_value = 'bad'
        with self.assertRaises(input_mod.NoChoice):
            self.query('foo')
        self.assertEqual(fake_input.call_count, 3)
        self.assertEqual(
            self.err.get_text_stream().strip().split('\n')[1],
            "Sorry, response %r not understood." % (fake_input.return_value,))

    @patch.object(compat, 'input')
    def test_custom_choice_limit(self, fake_input):
        # user hits enters a bad choice 5 times in a row
        fake_input.return_value = 'haha'
        with self.assertRaises(input_mod.NoChoice):
            self.query('foo', limit=5)
        self.assertEqual(fake_input.call_count, 5)
        self.assertEqual(
            self.err.get_text_stream().strip().split('\n')[1],
            "Sorry, response %r not understood." % (fake_input.return_value,))
