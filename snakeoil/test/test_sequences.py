# Copyright: 2015 Tim Harder <radhermit@gmail.com>
# License: GPL2/BSD 3 clause

from itertools import chain
from unittest import TestCase

from snakeoil.sequences import namedtuple, split_negations


class TestNamedTuple(TestCase):

    def test_namedtuple(self):
        Point = namedtuple('Point', ('x', 'y', 'z'))

        p = Point(1, 2, 3)
        self.assertEqual(p.x, 1)
        self.assertEqual(p[0], 1)
        self.assertEqual(p.y, 2)
        self.assertEqual(p[1], 2)
        self.assertEqual(p.z, 3)
        self.assertEqual(p[2], 3)
        self.assertEqual(p, (1, 2, 3))
        self.assertTrue(isinstance(p, Point))
        self.assertTrue(isinstance(p, tuple))

        # namedtuples act like tuples
        q = Point(4, 5, 6)
        self.assertEqual(p + q, (1, 2, 3, 4, 5, 6))
        self.assertEqual(tuple(map(sum, zip(p, q))), (5, 7, 9))

        # tuples are immutable
        with self.assertRaises(AttributeError):
            p.x = 10
        with self.assertRaises(TypeError):
            p[0] = 10

        # our version of namedtuple doesn't support keyword args atm
        with self.assertRaises(TypeError):
            q = Point(x=1, y=2, z=3)


class TestSplitNegations(TestCase):

    def test_sequences(self):
        # empty input
        seq = ''
        self.assertEqual(split_negations(seq), (tuple(), tuple()))

        # no-value negation should raise a ValueError
        seq = 'a b c - d f e'.split()
        with self.assertRaises(ValueError):
            split_negations(seq)

        # all negs
        seq = ('-' + str(x) for x in xrange(100))
        self.assertEqual(split_negations(seq), (tuple(map(str, xrange(100))), tuple()))

        # all pos
        seq = (str(x) for x in xrange(100))
        self.assertEqual(split_negations(seq), (tuple(), tuple(map(str, xrange(100)))))

        # both
        seq = (('-' + str(x), str(x)) for x in xrange(100))
        seq = chain.from_iterable(seq)
        self.assertEqual(split_negations(seq), (tuple(map(str, xrange(100))), tuple(map(str, xrange(100)))))

        # converter method
        seq = (('-' + str(x), str(x)) for x in xrange(100))
        seq = chain.from_iterable(seq)
        self.assertEqual(split_negations(seq, int), (tuple(xrange(100)), tuple(xrange(100))))
