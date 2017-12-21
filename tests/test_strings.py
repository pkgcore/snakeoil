# Copyright: 2017 Tim Harder <radhermit@gmail.com>
# License: BSD/GPL2

from snakeoil.strings import pluralism
from snakeoil.test import TestCase


class TestPluralism(TestCase):

    def test_none(self):
        # default
        self.assertEqual(pluralism([]), 's')

        # different suffix for nonexistence
        self.assertEqual(pluralism([], none=''), '')

    def test_singular(self):
        # default
        self.assertEqual(pluralism([1]), '')

        # different suffix for singular existence
        self.assertEqual(pluralism([1], singular='o'), 'o')

    def test_plural(self):
        # default
        self.assertEqual(pluralism([1, 2]), 's')

        # different suffix for plural existence
        self.assertEqual(pluralism([1, 2], plural='ies'), 'ies')

    def test_int(self):
        self.assertEqual(pluralism(0), 's')
        self.assertEqual(pluralism(1), '')
        self.assertEqual(pluralism(2), 's')
