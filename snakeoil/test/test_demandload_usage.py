# Copyright: 2005 Brian Harring <ferringb@gmail.com>
# License: GPL2

import os, stat, errno

from snakeoil.test import TestCase

class TestDemandLoadTargets(TestCase):

    valid_inits = frozenset("__init__.%s" % x for x in ("py", "pyc", "pyo", "so"))

    target_namespace = 'snakeoil'
    ignore_all_import_failures = False

    def test_demandload_targets(self):
        for x in self.check_namespace(self.target_namespace,
            ignore_failed_imports=self.ignore_all_import_failures):
            self.check_space(x)

    def check_space(self, mod):
        for attr in dir(mod):
            try:
                obj = getattr(mod, attr)
                # force __getattribute__ to fire
                getattr(obj, "__class__", None)
            except ImportError, ie:
                # hit one.
                self.fail("failed 'touching' demandloaded %s.%s: error %s" %
                    (mod.__name__, attr, ie))

    def recurse(self, location, valid_namespace=True):
        l = os.listdir(location)
        if not self.valid_inits.intersection(l):
            if valid_namespace:
                return
        else:
            yield None

        stats = []
        for x in l:
            try:
                stats.append((x, os.stat(os.path.join(location, x)).st_mode))
            except OSError, oe:
                if oe.errno != errno.ENOENT:
                    raise
                # file disappeared under our feet... lock file from
                # trial can cause this.  ignore.
                import logging
                logging.warn("file %r disappeared under our feet, ignoring" %
                    (os.path.join(location, x)))

        seen = set(['__init__'])
        for (x, st) in stats:
            if not (x.startswith(".") or x.endswith("~")) and stat.S_ISREG(st):
                if (x.endswith(".py") or x.endswith(".pyc")
                    or x.endswith(".pyo") or x.endswith(".so")):
                    y = x.rsplit(".", 1)[0]
                    if y not in seen:
                        seen.add(y)
                        yield y

        for (x, st) in stats:
            if stat.S_ISDIR(st):
                for y in self.recurse(os.path.join(location, x)):
                    if y is None:
                        yield x
                    else:
                        yield "%s.%s" % (x, y)

    @staticmethod
    def poor_mans_load(namespace):
        obj = __import__(namespace)
        for chunk in namespace.split(".")[1:]:
            try:
                obj = getattr(obj, chunk)
            except (RuntimeError, SystemExit, KeyboardInterrupt):
                raise
            except AttributeError:
                raise AssertionError("failed importing target %s" % namespace)
            except Exception, e:
                raise AssertionError("failed importing target %s; error %s"
                    % (namespace, e))
        return obj

    def check_namespace(self, namespace, **kwds):
        location = os.path.abspath(os.path.dirname(
            self.poor_mans_load(namespace).__file__))
        return self.get_modules(self.recurse(location), namespace, **kwds)

    def check_toplevel(self, location, **kwds):
        return self.get_modules(self.recurse(location, False), **kwds)

    def get_modules(self, feed, namespace=None, ignore_failed_imports=False):
        if namespace is None:
            mangle = lambda x:x
        else:
            mangle = lambda x: "%s.%s" % (namespace, x)
        for x in feed:
            try:
                if x is None:
                    if namespace is None:
                        continue
                    yield self.poor_mans_load(namespace)
                else:
                    yield self.poor_mans_load(mangle(x))
            except ImportError:
                if not ignore_failed_imports:
                    raise
