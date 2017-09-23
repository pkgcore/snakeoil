# Copyright: 2006 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

import operator

from snakeoil.test import TestCase
from snakeoil.iterables import expandable_chain, caching_iter, iter_sort
from snakeoil import compatibility

class ExpandableChainTest(TestCase):

    def test_normal_function(self):
        i = [iter(xrange(100)) for x in xrange(3)]
        e = expandable_chain()
        e.extend(i)
        self.assertEqual(list(e), range(100)*3)
        for x in i + [e]:
            self.assertRaises(StopIteration, x.next)

    def test_extend(self):
        e = expandable_chain()
        e.extend(xrange(100) for i in (1, 2))
        self.assertEqual(list(e), range(100)*2)
        self.assertRaises(StopIteration, e.extend, [[]])

    def test_extendleft(self):
        e = expandable_chain(xrange(20, 30))
        e.extendleft([xrange(10, 20), xrange(10)])
        self.assertEqual(list(e), range(30))
        self.assertRaises(StopIteration, e.extendleft, [[]])

    def test_append(self):
        e = expandable_chain()
        e.append(xrange(100))
        self.assertEqual(list(e), range(100))
        self.assertRaises(StopIteration, e.append, [])

    def test_appendleft(self):
        e = expandable_chain(xrange(10, 20))
        e.appendleft(xrange(10))
        self.assertEqual(list(e), range(20))
        self.assertRaises(StopIteration, e.appendleft, [])


class CachingIterTest(TestCase):

    def test_iter_consumption(self):
        i = iter(xrange(100))
        c = caching_iter(i)
        i2 = iter(c)
        for _ in xrange(20):
            i2.next()
        self.assertEqual(i.next(), 20)
        # note we consumed one ourselves
        self.assertEqual(c[20], 21)
        list(c)
        self.assertRaises(StopIteration, i.next)
        self.assertEqual(list(c), range(20) + range(21, 100))

    def test_init(self):
        self.assertEqual(caching_iter(list(xrange(100)))[0], 0)

    def test_full_consumption(self):
        i = iter(xrange(100))
        c = caching_iter(i)
        self.assertEqual(list(c), range(100))
        # do it twice, to verify it returns properly
        self.assertEqual(list(c), range(100))

    def test_len(self):
        self.assertEqual(100, len(caching_iter(xrange(100))))

    def test_hash(self):
        self.assertEqual(hash(caching_iter(xrange(100))),
                         hash(tuple(range(100))))

    def test_nonzero(self):
        c = caching_iter(xrange(100))
        self.assertEqual(bool(c), True)
        # repeat to check if it works when cached.
        self.assertEqual(bool(c), True)
        self.assertEqual(bool(caching_iter(iter([]))), False)

    @staticmethod
    def _py3k_protection(*args, **kwds):
        ci = caching_iter(*args, **kwds)
        if compatibility.is_py3k:
            ci = tuple(ci)
        return ci

    def test_cmp(self):
        get_inst = self._py3k_protection
        self.assertEqual(get_inst(xrange(100)), tuple(xrange(100)))
        self.assertNotEqual(get_inst(xrange(90)), tuple(xrange(100)))
        self.assertTrue(get_inst(xrange(100)) > tuple(xrange(90)))
        self.assertFalse(get_inst(xrange(90)) > tuple(xrange(100)))
        self.assertTrue(get_inst(xrange(100)) >= tuple(xrange(100)))
        self.assertTrue(get_inst(xrange(90)) < tuple(xrange(100)))
        self.assertFalse(get_inst(xrange(100)) < tuple(xrange(90)))
        self.assertTrue(get_inst(xrange(90)) <= tuple(xrange(100)))

    def test_sorter(self):
        get_inst = self._py3k_protection
        self.assertEqual(
            get_inst(xrange(100, 0, -1), sorted), tuple(xrange(1, 101)))
        c = caching_iter(xrange(100, 0, -1), sorted)
        self.assertTrue(c)
        if compatibility.is_py3k:
            c = tuple(c)
        self.assertEqual(c, tuple(xrange(1, 101)))
        c = caching_iter(xrange(50, 0, -1), sorted)
        self.assertEqual(c[10], 11)
        if compatibility.is_py3k:
            c = tuple(c)
        self.assertEqual(tuple(xrange(1, 51)), c)

    def test_getitem(self):
        c = caching_iter(xrange(20))
        self.assertEqual(19, c[-1])
        self.assertRaises(IndexError, operator.getitem, c, -21)
        self.assertRaises(IndexError, operator.getitem, c, 21)

    def test_edgecase(self):
        c = caching_iter(xrange(5))
        self.assertEqual(c[0], 0)
        # do an off by one access- this actually has broke before
        self.assertEqual(c[2], 2)
        self.assertEqual(c[1], 1)
        self.assertEqual(list(c), list(xrange(5)))

    def test_setitem(self):
        self.assertRaises(
            TypeError, operator.setitem, caching_iter(xrange(10)), 3, 4)

    def test_str(self):
        # Just make sure this works at all.
        self.assertTrue(str(caching_iter(xrange(10))))


class iter_sortTest(TestCase):
    def test_ordering(self):
        def f(l):
            return sorted(l, key=operator.itemgetter(0))
        self.assertEqual(
            list(iter_sort(
                f, *[iter(xrange(x, x + 10)) for x in (30, 20, 0, 10)])),
            list(xrange(40)))
