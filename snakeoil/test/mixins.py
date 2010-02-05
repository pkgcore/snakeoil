# Copyright: 2005 Marien Zwart <marienz@gentoo.org>
# Copyright: 2009 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2


import os
import shutil
import tempfile

from snakeoil.test import TestCase
from snakeoil import compatibility

class TempDirMixin(TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        # force it, since sticky bits spread.
        os.chmod(self.dir, 0700)

    def tearDown(self):
        # change permissions back or rmtree can't kill it
        for root, dirs, files in os.walk(self.dir):
            for directory in dirs:
                os.chmod(os.path.join(root, directory), 0777)
        shutil.rmtree(self.dir)

def tempdir_decorator(func):
    def f(self, *args, **kwargs):
        self.dir = tempfile.mkdtemp()
        try:
            os.chmod(self.dir, 0700)
            return func(self, *args, **kwargs)
        finally:
            for root, dirs, files in os.walk(self.dir):
                for directory in dirs:
                    os.chmod(os.path.join(root, directory), 0777)
            shutil.rmtree(self.dir)
    f.__name__ = func.__name__
    return f

mk_named_tempfile = tempfile.NamedTemporaryFile
if compatibility.is_py3k:
    import io
    def mk_named_tempfile(*args, **kwds):
        tmp_f = tempfile.NamedTemporaryFile(*args, **kwds)
        return io.TextIOWrapper(tmp_f)

# Copyright: 2005 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

import os, stat, errno

from snakeoil.test import TestCase
from snakeoil import compatibility

class PythonNamespaceWalker(object):

    target_namespace = None
    ignore_all_import_failures = False

    valid_inits = frozenset("__init__.%s" % x for x in ("py", "pyc", "pyo", "so"))

    module_blacklist = frozenset()

    def _default_module_blacklister(self, target):
        return target in self.module_blacklist

    def walk_namespace(self, namespace, **kwds):
        location = os.path.abspath(os.path.dirname(
            self.poor_mans_load(namespace).__file__))
        return self.get_modules(self.recurse(location), namespace=namespace,
            **kwds)

    def get_modules(self, feed, namespace=None, blacklist_func=None,
        ignore_failed_imports=None):
        if ignore_failed_imports is None:
            ignore_failed_imports = self.ignore_all_import_failures
        if namespace is None:
            mangle = lambda x:x
        else:
            orig_namespace = namespace
            mangle = lambda x: "%s.%s" % (orig_namespace, x)
        if blacklist_func is None:
            blacklist_func = self._default_module_blacklister
        for mod_name in feed:
            try:
                if mod_name is None:
                    if namespace is None:
                        continue
                else:
                    namespace = mangle(mod_name)
                if blacklist_func(namespace):
                    continue
                yield self.poor_mans_load(namespace)
            except ImportError:
                if not ignore_failed_imports:
                    raise

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


class SubclassWalker(object):

    target_namespace = None
    cls_blacklist = frozenset()

    def is_blacklisted(self, cls):
        return cls.__name__ in self.cls_blacklist

    def walk_derivatives(self, cls, seen=None):
        if cls == type:
            return
        if seen is None:
            seen = set()
        pos = 0
        for pos, subcls in enumerate(cls.__subclasses__()):
            if subcls in seen:
                continue
            seen.add(subcls)
            if self.is_blacklisted(subcls):
                continue
            for grand_daddy in self.walk_derivatives(subcls, seen):
                yield grand_daddy
        if pos == 0:
            yield cls
