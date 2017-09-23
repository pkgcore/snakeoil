# Copyright: 2015-2016 Tim Harder <radhermit@gmail.com>
# Copyright: 2005 Marien Zwart <marienz@gentoo.org>
# License: GPL2/BSD 3 clause

from collections import OrderedDict
from itertools import chain
from operator import itemgetter
import unittest

from snakeoil import sequences
from snakeoil.sequences import namedtuple, split_negations
from snakeoil.test import TestCase, mk_cpy_loadable_testcase


class UnhashableComplex(complex):

    def __hash__(self):
        raise TypeError


class UniqueTest(TestCase):

    def common_check(self, func):
        # silly
        self.assertEqual(func(()), [])
        # hashable
        self.assertEqual(sorted(func([1, 1, 2, 3, 2])), [1, 2, 3])
        # neither

    def test_stable_unique(self, func=sequences.stable_unique):
        self.assertEqual(
            list(set([1, 2, 3])), [1, 2, 3],
            "this test is reliant on the interpretter hasing 1,2,3 into a specific ordering- "
            "for whatever reason, ordering differs, thus this test can't verify it")
        self.assertEqual(func([3, 2, 1]), [3, 2, 1])

    def test_iter_stable_unique(self):
        self.test_stable_unique(lambda x: list(sequences.iter_stable_unique(x)))
        o = UnhashableComplex()
        l = [1, 2, 3, o, UnhashableComplex(), 4, 3, UnhashableComplex()]
        self.assertEqual(list(sequences.iter_stable_unique(l)),
                         [1, 2, 3, o, 4])

    def _generator(self):
        for x in xrange(5, -1, -1):
            yield x

    def test_unstable_unique(self):
        self.common_check(sequences.unstable_unique)
        uc = UnhashableComplex
        res = sequences.unstable_unique([uc(1, 0), uc(0, 1), uc(1, 0)])
        # sortable
        self.assertEqual(sorted(sequences.unstable_unique(
            [[1, 2], [1, 3], [1, 2], [1, 3]])), [[1, 2], [1, 3]])
        self.assertTrue(
            res == [uc(1, 0), uc(0, 1)] or res == [uc(0, 1), uc(1, 0)], res)
        self.assertEqual(sorted(sequences.unstable_unique(self._generator())),
                         sorted(xrange(6)))


class ChainedListsTest(TestCase):

    @staticmethod
    def gen_cl():
        return sequences.ChainedLists(range(3), range(3, 6), range(6, 100))

    def test_contains(self):
        cl = self.gen_cl()
        for x in (1, 2, 4, 99):
            self.assertTrue(x in cl)

    def test_iter(self):
        self.assertEqual(list(self.gen_cl()), list(xrange(100)))

    def test_len(self):
        self.assertEqual(100, len(self.gen_cl()))

    def test_str(self):
        l = sequences.ChainedLists(range(3), range(3, 5))
        self.assertEqual(str(l), '[ [0, 1, 2], [3, 4] ]')

    def test_getitem(self):
        cl = self.gen_cl()
        for x in (1, 2, 4, 98, -1, -99, 0):
            # "Statement seems to have no effect"
            # pylint: disable=W0104
            cl[x]
        self.assertRaises(IndexError, cl.__getitem__, 100)
        self.assertRaises(IndexError, cl.__getitem__, -101)

    def test_mutable(self):
        self.assertRaises(TypeError, self.gen_cl().__delitem__, 1)
        self.assertRaises(TypeError, self.gen_cl().__setitem__, 1, 2)

    def test_append(self):
        cl = self.gen_cl()
        cl.append(range(10))
        self.assertEqual(110, len(cl))

    def test_extend(self):
        cl = self.gen_cl()
        cl.extend(range(10) for i in range(5))
        self.assertEqual(150, len(cl))


class Test_iflatten_instance(TestCase):
    func = staticmethod(sequences.native_iflatten_instance)

    def test_it(self):
        o = OrderedDict((k, None) for k in xrange(10))
        for l, correct, skip in (
                (["asdf", ["asdf", "asdf"], 1, None],
                 ["asdf", "asdf", "asdf", 1, None], basestring),
                ([o, 1, "fds"], [o, 1, "fds"], (basestring, OrderedDict)),
                ([o, 1, "fds"], range(10) + [1, "fds"], basestring),
                ("fds", ["fds"], basestring),
                ("fds", ["f", "d", "s"], int),
                ('', [''], basestring),
                (1, [1], int),
                ):
            iterator = self.func(l, skip)
            self.assertEqual(list(iterator), correct)
            self.assertEqual([], list(iterator))

        # There is a small difference between the cpython and native
        # version: the cpython one raises immediately, for native we
        # have to iterate.
        def fail():
            return list(self.func(None))
        self.assertRaises(TypeError, fail)

        # Yes, no sane code does this, but even insane code shouldn't
        # kill the cpython version.
        iters = []
        iterator = self.func(iters)
        iters.append(iterator)
        self.assertRaises(ValueError, iterator.next)

        # Regression test: this was triggered through demandload.
        # **{} is there to explicitly force a dict.
        self.assertTrue(self.func((), **{}))


class Test_iflatten_func(TestCase):
    func = staticmethod(sequences.native_iflatten_func)

    def test_it(self):
        o = OrderedDict((k, None) for k in xrange(10))
        for l, correct, skip in (
                (["asdf", ["asdf", "asdf"], 1, None],
                 ["asdf", "asdf", "asdf", 1, None], basestring),
                ([o, 1, "fds"], [o, 1, "fds"], (basestring, OrderedDict)),
                ([o, 1, "fds"], range(10) + [1, "fds"], basestring),
                ("fds", ["fds"], basestring),
                (1, [1], int),
                ):
            iterator = self.func(l, lambda x: isinstance(x, skip))
            self.assertEqual(list(iterator), correct)
            self.assertEqual(list(iterator), [])

        # There is a small difference between the cpython and native
        # version: the cpython one raises immediately, for native we
        # have to iterate.
        def fail():
            return list(self.func(None, lambda x: False))
        self.assertRaises(TypeError, fail)

        # Yes, no sane code does this, but even insane code shouldn't
        # kill the cpython version.
        iters = []
        iterator = self.func(iters, lambda x: False)
        iters.append(iterator)
        self.assertRaises(ValueError, iterator.next)

        # Regression test: this was triggered through demandload.
        # **{} is there to explicitly force a dict to the underly cpy
        self.assertTrue(self.func((), lambda x: True, **{}))


class CPY_Test_iflatten_instance(Test_iflatten_instance):
    func = staticmethod(sequences.iflatten_instance)
    if not sequences.cpy_builtin:
        skip = "cpython extension isn't available"


class CPY_Test_iflatten_func(Test_iflatten_func):
    func = staticmethod(sequences.iflatten_func)
    if not sequences.cpy_builtin:
        skip = "cpython extension isn't available"


class predicate_split_Test(TestCase):
    kls = staticmethod(sequences.predicate_split)

    def test_simple(self):
        false_l, true_l = self.kls(lambda x: x % 2 == 0, xrange(100))
        self.assertEqual(false_l, range(1, 100, 2))
        self.assertEqual(true_l, range(0, 100, 2))

    def test_key(self):
        false_l, true_l = self.kls(lambda x: x % 2 == 0,
                                   ([0, x] for x in xrange(100)),
                                   key=itemgetter(1))
        self.assertEqual(false_l, [[0, x] for x in xrange(1, 100, 2)])
        self.assertEqual(true_l, [[0, x] for x in range(0, 100, 2)])

cpy_loaded_Test = mk_cpy_loadable_testcase(
    "snakeoil._sequences", "snakeoil.sequences", "iflatten_func", "iflatten_func")


class TestNamedTuple(unittest.TestCase):

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


class TestSplitNegations(unittest.TestCase):

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
