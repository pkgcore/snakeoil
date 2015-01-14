# Copyright: 2010-2011 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD 3 clause

from snakeoil.test import mixins, TestCase


class Test(mixins.TargetedNamespaceWalker, mixins.KlassWalker, TestCase):

    target_namespace = 'snakeoil'

    singleton = object()

    def setUp(self):
        self._ignore_set = frozenset(self.iter_builtin_targets())

    def _should_ignore(self, cls):
        if cls in self._ignore_set:
            return True

        if getattr(cls, "__hash__intentionally_disabled__", False):
            return True

        namepath = "%s.%s" % (cls.__module__, cls.__name__)
        return not namepath.startswith(self.target_namespace)

    def run_check(self, cls):
        for parent in cls.__bases__:
            if parent == object:
                # object sets __hash__/__eq__, which isn't usually
                # intended to be inherited/reused
                continue
            eq = getattr(parent, '__eq__', self.singleton)
            h = getattr(parent, '__hash__', self.singleton)
            if eq == object.__eq__ and h == object.__hash__:
                continue
            if eq and h:
                break
        else:
            return

        # pylint: disable=undefined-loop-variable
        # 'parent' is guaranteed to be defined due to the 'else' clause above
        self.assertNotEqual(getattr(cls, '__hash__'), None, msg=(
            "class '%s.%s' had its __hash__ reset, while it would've inherited "
            "__hash__ from parent '%s.%s'; this occurs in py3k when __eq__ is "
            "defined alone.  If this is desired behaviour, set "
            "__hash__intentionally_disabled__ to True to explicitly ignore this"
            " class" % (cls.__module__, cls.__name__, parent.__module__,
                        parent.__name__)))
