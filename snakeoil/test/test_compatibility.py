# Copyright: 2006 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

from snakeoil.test import TestCase
from snakeoil import compatibility
from snakeoil.currying import post_curry
from operator import itemgetter
import __builtin__ as builtins

class override_mixin(object):

    def test_builtin_override(self):
        if not self.was_missing:
            self.assertIdentical(getattr(builtins, self.override_name),
                                 getattr(compatibility, self.override_name))


class CmpTest(TestCase, override_mixin):

    was_missing = compatibility.is_py3k
    override_name = 'cmp'

    func = staticmethod(compatibility.cmp)

    if was_missing:
        def test_it(self):
            f = self.func
            self.assertTrue(f(1, 2) < 0)
            self.assertTrue(f(1, 1) == 0)
            self.assertTrue(f(2, 1) > 0)
            self.assertTrue(f(1, None) > 0)
            self.assertTrue(f(None, 1) < 0)
            self.assertTrue(f(None, None) == 0)


class NextTest(TestCase):

    # done this way to keep 2to3 from mangling the name invalidly.
    func = staticmethod(getattr(compatibility, 'next'))

    def test_it(self):
        f = self.func
        self.assertRaises(TypeError, f, None)
        self.assertRaises(TypeError, f, "s")
        i = iter("sa")
        self.assertEqual(f(i), "s")
        self.assertEqual(f(i), "a")
        self.assertRaises(StopIteration, f, i)


class incomparable_obj(tuple):
    # used to ensure that if this raw object is compared,
    # it goes boom.

    # this is needed to avoid a false positive in a test for py2k->py3k
    # conversion errors; we don't care about it since this is just a mock.
    __hash__intentionally_disabled__ = True

    def __le__(self, other):
        raise TypeError

    __eq__ = __ne__ = __cmp__ = __le__


class sorted_cmp_test(TestCase):

    func = staticmethod(compatibility.sorted_cmp)

    unchanging = True

    @staticmethod
    def get_list():
        return range(100)

    def test_it(self):
        f = self.func
        l = self.get_list()
        cmp = compatibility.cmp
        self.assertEqual(sorted(l, reverse=True),
            f(l, lambda x, y:-cmp(x,y)))

        if self.unchanging:
            self.assertEqual(self.get_list(), l)

        l = list(reversed(self.get_list()))
        self.assertEqual(sorted(l),
            f(l, cmp))

        if self.unchanging:
            self.assertEqual(list(reversed(self.get_list())), l)

        zeroth = itemgetter(0)

        l = self.get_list()
        mangled = [incomparable_obj([x]) for x in l]
        # finally, verify it combines key w/ cmp properly.
        self.assertEqual(sorted(l, reverse=True),
            map(zeroth, f(mangled, (lambda x, y:cmp(x,y)), key=zeroth,
                reverse=True)))

        if self.unchanging:
            self.assertEqual(self.get_list(), map(zeroth, mangled))


class sort_cmp_test(TestCase):

    unchanging = False
    func = staticmethod(compatibility.sort_cmp)


class BytesTest(TestCase):

    func = staticmethod(compatibility.force_bytes)

    def test_conversion(self):
        if compatibility.is_py3k:
            kls = bytes
        else:
            kls = str
        self.assertEqual(self.func("adsf"), "adsf".encode())
        self.assertTrue(isinstance(self.func("adsf"), kls))


class Is_DisjointTest(TestCase):
    func = staticmethod(compatibility.is_disjoint)

    def test_compat(self):
        s = set(xrange(5))
        s2 = set(xrange(5, 10))
        self.assertTrue(self.func(s, s2))
        self.assertFalse(self.func(s, s))


class raise_from_test(TestCase):

    func = staticmethod(compatibility.raise_from)

    def test_it(self):
        def f():
            raise KeyError(1)

        def f2():
            try:
                f()
            except KeyError:
                self.func(IndexError(1))

        self.assertRaises(IndexError, f2)
        try:
            f2()
        except IndexError, e:
            self.assertTrue(hasattr(e, '__cause__'))
            self.assertTrue(isinstance(e.__cause__, KeyError))
