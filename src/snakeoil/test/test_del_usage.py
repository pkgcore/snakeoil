# Copyright: 2010 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD 3 clause

import sys

from snakeoil.test import mixins, TestCase, SkipTest
from snakeoil.weakrefs import WeakRefFinalizer

class Test(mixins.TargetedNamespaceWalker, mixins.KlassWalker, TestCase):

    target_namespace = 'snakeoil'

    def setUp(self):
        self._ignore_set = frozenset(self.iter_builtin_targets())

    def _should_ignore(self, cls):
        if cls in self._ignore_set:
            return True

        namepath = "%s.%s" % (cls.__module__, cls.__name__)
        return not namepath.startswith(self.target_namespace)

    def run_check(self, cls):
        if sys.hexversion >= 0x03040000:
            raise SkipTest("WeakRefFinalizer is unnecessary in python-3.4 and later")

        if not hasattr(cls, '__del__') or getattr(cls, '__allow_del__', False):
            return

        name = "%s.%s" % (cls.__module__, cls.__name__)

        self.assertTrue(issubclass(cls, WeakRefFinalizer), msg=(
            "class %s has a __del__ method, but should be using "
            "weakrefs.WeakRefFinalizer to avoid gc cycle issues.  If "
            "WeakRefFinalizer isn't an option, set __allow_del__ in the cls "
            "namespace to True" % (name,)))
        self.assertFalse(hasattr(cls, '__del__'), msg=(
            "class %s uses metaclass WeakRefFinalizer but still somehow "
            "has a __del__ method rather than a __finalizer__; this shouldn't "
            "be possible."))
        self.assertTrue(hasattr(cls, '__finalizer__'), msg=(
            "class %s uses metaclass WeakRefFinalizer but has no "
            "__finalizer__ method; this means the class doesn't need "
            "finalizing.  Likely shouldn't be using WeakRefFinalizer"))
