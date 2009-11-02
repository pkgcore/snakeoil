# Copyright: 2006 Brian Harring <ferringb@gmail.com>
# License: GPL2

from snakeoil.test import TestCase
from snakeoil import compatibility
from snakeoil.currying import post_curry
import __builtin__ as builtins

class mixin(object):
    was_missing = (not compatibility.is_py3k) and not hasattr(builtins, 'any')

    def test_builtin_override(self):
        if not self.was_missing:
            self.assertIdentical(getattr(builtins, self.override_name),
                                 getattr(compatibility, self.override_name))

    def check_func(self, name, result1, result2, test3, result3):
        i = iter(xrange(100))
        f = getattr(compatibility, name)
        self.assertEqual(f(x==3 for x in i), result1)
        self.assertEqual(i.next(), result2)
        self.assertEqual(f(test3), result3)


class AnyTest(TestCase, mixin):
    override_name = "any"

    if mixin.was_missing:
        test_native_any = post_curry(mixin.check_func,
            "native_any", True, 4, (x==3 for x in xrange(2)), False)
        test_cpy_any = post_curry(mixin.check_func,
            "any", True, 4, (x==3 for x in xrange(2)), False)

        if compatibility.native_any is compatibility.any:
            test_cpy_any.skip = "cpy extension not available"



class AllTest(TestCase, mixin):
    override_name = "all"

    if mixin.was_missing:
        test_native_all = post_curry(mixin.check_func,
            "native_all", False, 1,
                (isinstance(x, int) for x in xrange(100)), True)

        test_cpy_all = post_curry(mixin.check_func,
            "all", False, 1,
                (isinstance(x, int) for x in xrange(100)), True)

        if compatibility.native_all is compatibility.all:
            test_cpy_all.skip = "cpy extension not available"
