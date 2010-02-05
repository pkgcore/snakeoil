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

class anyallmixin(object):

    was_missing = (not compatibility.is_py3k) and not hasattr(builtins, 'any')

    def check_func(self, name, result1, result2, test3, result3):
        i = iter(xrange(100))
        f = getattr(compatibility, name)
        self.assertEqual(f(x==3 for x in i), result1)
        self.assertEqual(i.next(), result2)
        self.assertEqual(f(test3), result3)


class AnyTest(TestCase, override_mixin, anyallmixin):
    override_name = "any"

    if anyallmixin.was_missing:
        test_native_any = post_curry(anyallmixin.check_func,
            "native_any", True, 4, (x==3 for x in xrange(2)), False)
        test_cpy_any = post_curry(anyallmixin.check_func,
            "any", True, 4, (x==3 for x in xrange(2)), False)

        if compatibility.native_any is compatibility.any:
            test_cpy_any.skip = "cpy extension not available"



class AllTest(TestCase, override_mixin, anyallmixin):
    override_name = "all"

    if anyallmixin.was_missing:
        test_native_all = post_curry(anyallmixin.check_func,
            "native_all", False, 1,
                (isinstance(x, int) for x in xrange(100)), True)

        test_cpy_all = post_curry(anyallmixin.check_func,
            "all", False, 1,
                (isinstance(x, int) for x in xrange(100)), True)

        if compatibility.native_all is compatibility.all:
            test_cpy_all.skip = "cpy extension not available"


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
