# Copyright: 2006 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

from weakref import WeakValueDictionary

from snakeoil.test import TestCase
from snakeoil.weakrefs import WeakValCache

class RefObj(object):
    pass

class TestWeakValCache(TestCase):
    if WeakValueDictionary is WeakValCache:
        skip = "WeakValCache is weakref.WeakValueDictionary; indicates " \
            "snakeoil._caching isn't compiled"

    def setUp(self):
        self.o = RefObj()
        self.w = WeakValCache()

    def test_setitem(self):
        s = "asdf"
        self.w[s] = self.o
        self.w["fds"] = self.o
        self.w[s] = self.o

    def test_getitem(self):
        s = "asdf"
        self.w[s] = self.o
        self.assertIdentical(self.w[s], self.o)

    def test_expiring(self):
        s = "asdf"
        self.w[s] = self.o
        self.assertTrue(self.w[s])
        del self.o
        self.assertRaises(KeyError, self.w.__getitem__, s)

    def test_get(self):
        s = "asdf"
        self.assertRaises(KeyError, self.w.__getitem__, s)
        self.w[s] = self.o
        self.assertIdentical(self.w.get(s), self.o)

    def test_keys(self):
        self.assertEqual(list(self.w.keys()), [])
        self.w['a'] = self.o
        self.w['b'] = self.o
        self.w['c'] = self.o
        self.assertEqual(sorted(self.w.keys()), ['a', 'b', 'c'])
        del self.o
        self.assertEqual(sorted(self.w.keys()), [])

    def test_values(self):
        self.assertEqual(self.w.values(), [])
        self.w['a'] = self.o
        self.w['b'] = self.o
        self.w['c'] = self.o
        self.assertEqual(len(self.w.values()), 3)
        del self.o
        self.assertEqual(sorted(self.w.values()), [])

    def test_items(self):
        self.assertEqual(self.w.items(), [])
        self.w['a'] = self.o
        self.w['b'] = self.o
        self.w['c'] = self.o
        self.assertEqual(len(self.w.items()), 3)
        del self.o
        self.assertEqual(sorted(self.w.items()), [])
