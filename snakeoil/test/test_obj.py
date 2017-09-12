# Copyright: 2006-2011 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

import unittest

from snakeoil.test import TestCase
from snakeoil import obj

# sorry, but the name is good, just too long for these tests
make_DI = obj.DelayedInstantiation
make_DIkls = obj.DelayedInstantiation_kls
from snakeoil.compatibility import cmp

class TestDelayedInstantiation(TestCase):

    def test_simple(self):
        t = tuple([1, 2, 3])
        o = make_DI(tuple, lambda: t)
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
        def assertKls(cls, ignores=(),
                      default_ignores=("__new__", "__init__", "__init_subclass__",
                                       "__getattribute__", "__class__",
                                       "__getnewargs__", "__doc__")):
            required = set(x for x in dir(cls)
                           if x.startswith("__") and x.endswith("__"))
            missing = required.difference(obj.kls_descriptors)
            missing.difference_update(obj.base_kls_descriptors)
            missing.difference_update(default_ignores)
            missing.difference_update(ignores)
            self.assertFalse(missing, msg=(
                "object %r potentially has unsupported special "
                "attributes: %s" % (cls, ', '.join(missing))))

        assertKls(object)
        assertKls(1)
        assertKls(object())
        assertKls(list)
        assertKls({})
        assertKls(set())

    def test_BaseDelayedObject(self):
        # assert that all methods/descriptors of object
        # are covered via the base.
        o = set(dir(object)).difference("__%s__" % x for x in [
            "class", "getattribute", "new", "init", "init_subclass", "doc"])
        diff = o.difference(obj.base_kls_descriptors)
        self.assertFalse(diff, msg=(
            "base delayed instantiation class should cover all of object, but "
            "%r was spotted" % (",".join(sorted(diff)),)))
        self.assertEqual(obj.DelayedInstantiation_kls(int, "1") + 2, 3)


    def test_klass_choice_optimization(self):
        """ensure that BaseDelayedObject is used whenever possible"""

        # note object is an odd one- it actually has a __doc__, thus
        # it must always be a custom
        o = make_DI(object, object)
        self.assertNotIdentical(object.__getattribute__(o, '__class__'),
                                obj.BaseDelayedObject)
        class foon(object):
            pass
        o = make_DI(foon, foon)
        cls = object.__getattribute__(o, '__class__')
        self.assertIdentical(cls, obj.BaseDelayedObject)

        # now ensure we always get the same kls back for derivatives
        class foon(object):
            def __nonzero__(self):
                return True

        o = make_DI(foon, foon)
        cls = object.__getattribute__(o, '__class__')
        self.assertNotIdentical(cls, obj.BaseDelayedObject)
        o = make_DI(foon, foon)
        cls2 = object.__getattribute__(o, '__class__')
        self.assertIdentical(cls, cls2)

    def test__class__(self):
        l = []
        def f():
            l.append(False)
            return True
        o = make_DI(bool, f)
        self.assertTrue(isinstance(o, bool))
        self.assertFalse(l, "accessing __class__ shouldn't trigger "
                            "instantiation")

    def test__doc__(self):
        l = []
        def f():
            l.append(True)
            return foon()
        class foon(object):
            __doc__ = "monkey"

        o = make_DI(foon, f)
        self.assertEqual(o.__doc__, 'monkey')
        self.assertFalse(l,
                         "in accessing __doc__, the instance was generated- "
                         "this is a class level attribute, thus shouldn't "
                         "trigger instantiation")


class TestPopattr(unittest.TestCase):

    class Object(object):
        pass

    def test_popattr(self):
        o = self.Object()

        # object without any attrs
        with self.assertRaises(AttributeError):
            obj.popattr(o, 'nonexistent')

        o.test = 1

        # object with attr trying to get nonexistent attr
        with self.assertRaises(AttributeError):
            obj.popattr(o, 'nonexistent')

        # object with attr trying to get nonexistent attr using fallback
        value = obj.popattr(o, 'nonexistent', 2)
        self.assertEqual(value, 2)

        value = obj.popattr(o, 'test')
        self.assertEqual(value, 1)
        # verify that attr was removed from the object
        with self.assertRaises(AttributeError):
            obj.popattr(o, 'test')
