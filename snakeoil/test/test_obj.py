# Copyright: 2006 Brian Harring <ferringb@gmail.com>
# License: GPL2


import operator

from snakeoil.test import TestCase
from snakeoil import obj

# sorry, but the name is good, just too long for these tests
make_DI = obj.DelayedInstantiation
make_DIkls = obj.DelayedInstantiation_kls
from snakeoil.compatibility import cmp

class TestDelayedInstantiation(TestCase):

    def test_simple(self):
        t = tuple([1, 2, 3])
        o = make_DI(tuple, lambda:t)
        objs = [o, t]
        self.assertEqual(*map(str, objs))
        self.assertEqual(*map(repr, objs))
        self.assertEqual(*map(hash, objs))
        self.assertEqual(*objs)
        self.assertTrue(cmp(t, o) == 0)
        self.assertFalse(t < o)
        self.assertTrue(t <= o)
        self.assertTrue(t == o)
        self.assertTrue(t >= o)
        self.assertFalse(t > o)
        self.assertFalse(t != o)


    def test_descriptor_awareness(self):
        o = set(obj.kls_descriptors.difference(dir(object)))
        o.difference_update(dir(1))
        o.difference_update(dir('s'))
        o.difference_update(dir(list))
        o.difference_update(dir({}))

    def test_BaseDelayedObject(self):
        # assert that all methods/descriptors of object
        # are covered via the base.
        o = set(dir(object)).difference("__%s__" % x for x in
            ["class", "getattribute", "new", "init"])
        diff = o.difference(obj.base_kls_descriptors)
        self.assertEqual(set(), diff)

    def test__class__(self):
        l = []
        def f():
            l.append(False)
            return True
        o = make_DI(bool, f)
        self.assertTrue(isinstance(o, bool))
        self.assertFalse(l)


SporkDict = obj.make_SlottedDict_kls(['spork'])


class SlottedDictTest(TestCase):

    def test_exceptions(self):
        d = SporkDict()
        for op in (operator.getitem, operator.delitem):
            self.assertRaises(KeyError, op, d, 'spork')
            self.assertRaises(KeyError, op, d, 'foon')
