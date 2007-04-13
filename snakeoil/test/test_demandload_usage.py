# Copyright: 2005 Brian Harring <ferringb@gmail.com>
# License: GPL2

import os, stat

from snakeoil.test import TestCase

class TestDemandLoadTargets(TestCase):

    valid_inits = frozenset("__init__.%s" % x for x in ("py", "pyc", "pyo", "so"))

    target_namespace = 'snakeoil'
    ignore_all_import_failures = False

    def test_demandload_targets(self):
        for x in self.get_modules(self.target_namespace,
            self.ignore_all_import_failures):
            self.check_space(x)

    def check_space(self, mod):
        for attr in dir(mod):
            try:
                obj = getattr(mod, attr)
                # force __getattribute__ to fire
                getattr(obj, "__class__", None)
            except ImportError:
                # hit one.
                self.fail("failed 'touching' demandloaded %s.%s" %
                    (mod.__name__, attr))

    def recurse(self, location, require_init=True):
        l = os.listdir(location)
        if require_init and not self.valid_inits.intersection(l):
            return

        stats = [(x, os.stat(os.path.join(location, x)).st_mode) for x in l]
        seen = set(['__init__'])
        for (x, st) in stats:
            if stat.S_ISREG(st):
                if (x.endswith(".py") or x.endswith(".pyc")
                    or x.endswith(".pyo") or x.endswith(".so")):
                    y = x.rsplit(".", 1)[0]
                    if y not in seen:
                        seen.add(y)
                        yield y

        for (x, st) in stats:
            if stat.S_ISDIR(st):
                for y in self.recurse(os.path.join(location, x)):
                    yield "%s.%s" % (x, y)
                yield x

    @staticmethod
    def poor_mans_load(namespace):
        return reduce(getattr, namespace.split(".")[1:], __import__(namespace))

    def get_modules(self, namespace, ignore_failed_imports=False):
        try:
            i = self.poor_mans_load(namespace)
            yield i
        except ImportError:
            if ignore_failed_imports:
                return
            raise
        fn = i.__file__
        if not fn.rsplit(".", 1)[0].endswith("__init__"):
            yield namespace
            return
        for x in self.recurse(os.path.abspath(os.path.dirname(i.__file__))):
            try:
                yield self.poor_mans_load("%s.%s" % (i.__name__, x))
            except ImportError:
                if not ignore_failed_imports:
                    raise
