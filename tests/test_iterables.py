# Copyright: 2006 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

import operator

from snakeoil.iterables import expandable_chain, caching_iter, iter_sort
from snakeoil.test import TestCase


class ExpandableChainTest(TestCase):

    def test_normal_function(self):
        i = [iter(range(100)) for x in range(3)]
        e = expandable_chain()
        e.extend(i)
        self.assertEqual(list(e), list(range(100))*3)
        for x in i + [e]:
            self.assertRaises(StopIteration, x.__next__)

    def test_extend(self):
        e = expandable_chain()
        e.extend(range(100) for i in (1, 2))
        self.assertEqual(list(e), list(range(100))*2)
        self.assertRaises(StopIteration, e.extend, [[]])

    def test_extendleft(self):
        e = expandable_chain(range(20, 30))
        e.extendleft([range(10, 20), range(10)])
        self.assertEqual(list(e), list(range(30)))
        self.assertRaises(StopIteration, e.extendleft, [[]])

    def test_append(self):
        e = expandable_chain()
        e.append(range(100))
        self.assertEqual(list(e), list(range(100)))
        self.assertRaises(StopIteration, e.append, [])

    def test_appendleft(self):
        e = expandable_chain(range(10, 20))
        e.appendleft(range(10))
        self.assertEqual(list(e), list(range(20)))
        self.assertRaises(StopIteration, e.appendleft, [])


class CachingIterTest(TestCase):

    def test_iter_consumption(self):
        i = iter(range(100))
        c = caching_iter(i)
        i2 = iter(c)
        for _ in range(20):
            next(i2)
        self.assertEqual(next(i), 20)
        # note we consumed one ourselves
        self.assertEqual(c[20], 21)
        list(c)
        self.assertRaises(StopIteration, i.__next__)
        self.assertEqual(list(c), list(range(20)) + list(range(21, 100)))

    def test_init(self):
        self.assertEqual(caching_iter(list(range(100)))[0], 0)

    def test_full_consumption(self):
        i = iter(range(100))
        c = caching_iter(i)
        self.assertEqual(list(c), list(range(100)))
        # do it twice, to verify it returns properly
        self.assertEqual(list(c), list(range(100)))

    def test_len(self):
        self.assertEqual(100, len(caching_iter(range(100))))

    def test_hash(self):
        self.assertEqual(hash(caching_iter(range(100))),
                         hash(tuple(range(100))))

    def test_bool(self):
        c = caching_iter(range(100))
        self.assertEqual(bool(c), True)
        # repeat to check if it works when cached.
        self.assertEqual(bool(c), True)
        self.assertEqual(bool(caching_iter(iter([]))), False)

    @staticmethod
    def _py3k_protection(*args, **kwds):
        return tuple(caching_iter(*args, **kwds))

    def test_cmp(self):
        get_inst = self._py3k_protection
        self.assertEqual(get_inst(range(100)), tuple(range(100)))
        self.assertNotEqual(get_inst(range(90)), tuple(range(100)))
        self.assertTrue(get_inst(range(100)) > tuple(range(90)))
        self.assertFalse(get_inst(range(90)) > tuple(range(100)))
        self.assertTrue(get_inst(range(100)) >= tuple(range(100)))
        self.assertTrue(get_inst(range(90)) < tuple(range(100)))
        self.assertFalse(get_inst(range(100)) < tuple(range(90)))
        self.assertTrue(get_inst(range(90)) <= tuple(range(100)))

    def test_sorter(self):
        get_inst = self._py3k_protection
        self.assertEqual(
            get_inst(range(100, 0, -1), sorted), tuple(range(1, 101)))
        c = caching_iter(range(100, 0, -1), sorted)
        self.assertTrue(c)
        self.assertEqual(tuple(c), tuple(range(1, 101)))
        c = caching_iter(range(50, 0, -1), sorted)
        self.assertEqual(c[10], 11)
        self.assertEqual(tuple(range(1, 51)), tuple(c))

    def test_getitem(self):
        c = caching_iter(range(20))
        self.assertEqual(19, c[-1])
        self.assertRaises(IndexError, operator.getitem, c, -21)
        self.assertRaises(IndexError, operator.getitem, c, 21)

    def test_edgecase(self):
        c = caching_iter(range(5))
        self.assertEqual(c[0], 0)
        # do an off by one access- this actually has broke before
        self.assertEqual(c[2], 2)
        self.assertEqual(c[1], 1)
        self.assertEqual(list(c), list(range(5)))

    def test_setitem(self):
        self.assertRaises(
            TypeError, operator.setitem, caching_iter(range(10)), 3, 4)

    def test_str(self):
        # Just make sure this works at all.
        self.assertTrue(str(caching_iter(range(10))))


class iter_sortTest(TestCase):
    def test_ordering(self):
        def f(l):
            return sorted(l, key=operator.itemgetter(0))
        self.assertEqual(
            list(iter_sort(
                f, *[iter(range(x, x + 10)) for x in (30, 20, 0, 10)])),
            list(range(40)))
