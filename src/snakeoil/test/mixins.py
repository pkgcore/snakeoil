import errno
import inspect
import io
import os
import shutil
import stat
import sys
import tempfile

from . import TestCase
from ..compatibility import IGNORED_EXCEPTIONS


class TempDirMixin(TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        # force it, since sticky bits spread.
        os.chmod(self.dir, 0o700)

    def tearDown(self):
        # change permissions back or rmtree can't kill it
        if not os.path.exists(self.dir):
            return
        for root, dirs, _files in os.walk(self.dir):
            for directory in dirs:
                os.chmod(os.path.join(root, directory), 0o700)
        shutil.rmtree(self.dir)

def tempdir_decorator(func):
    def f(self, *args, **kwargs):
        self.dir = tempfile.mkdtemp()
        try:
            os.chmod(self.dir, 0o700)
            return func(self, *args, **kwargs)
        finally:
            if os.path.exists(self.dir):
                for root, dirs, _files in os.walk(self.dir):
                    for directory in dirs:
                        os.chmod(os.path.join(root, directory), 0o777)
                shutil.rmtree(self.dir)
    f.__name__ = func.__name__
    return f


def mk_named_tempfile(*args, **kwds):
    tmp_f = tempfile.NamedTemporaryFile(*args, **kwds)
    return io.TextIOWrapper(tmp_f)


class PythonNamespaceWalker:

    ignore_all_import_failures = False

    valid_inits = frozenset("__init__.%s" % x for x in ("py", "pyc", "pyo", "so"))

    # This is for py3.2/PEP3149; dso's now have the interp + major/minor embedded
    # in the name.
    # TODO: update this for pypy's naming
    abi_target = 'cpython-%i%i' % tuple(sys.version_info[:2])

    module_blacklist = frozenset([
        'snakeoil.cli.arghparse', 'snakeoil.pickling',
    ])

    def _default_module_blacklister(self, target):
        return target in self.module_blacklist or target.startswith('snakeoil.dist')

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
            mangle = lambda x: x
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

    def recurse(self, location, valid_namespace=True):
        if os.path.dirname(location) == '__pycache__':
            # Shouldn't be possible, but make sure we avoid this if it manages
            # to occur.
            return
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
            except OSError as oe:
                if oe.errno != errno.ENOENT:
                    raise
                # file disappeared under our feet... lock file from
                # trial can cause this.  ignore.
                import logging
                logging.debug("file %r disappeared under our feet, ignoring" %
                              (os.path.join(location, x)))

        seen = set(['__init__'])
        for (x, st) in stats:
            if not (x.startswith(".") or x.endswith("~")) and stat.S_ISREG(st):
                if (x.endswith(".py") or x.endswith(".pyc")
                        or x.endswith(".pyo") or x.endswith(".so")):
                    y = x.rsplit(".", 1)[0]
                    # Ensure we're not looking at a >=py3k .so which injects
                    # the version name in...
                    if y not in seen:
                        if '.' in y and x.endswith('.so'):
                            y, abi = x.rsplit('.', 1)
                            if abi != self.abi_target:
                                continue
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
    def poor_mans_load(namespace, existance_check=False):
        try:
            obj = __import__(namespace)
            if existance_check:
                return True
        except:
            if existance_check:
                return False
            raise
        for chunk in namespace.split(".")[1:]:
            try:
                obj = getattr(obj, chunk)
            except IGNORED_EXCEPTIONS:
                raise
            except AttributeError:
                raise AssertionError("failed importing target %s" % namespace)
            except Exception as e:
                raise AssertionError("failed importing target %s; error %s"
                                     % (namespace, e))
        return obj


class TargetedNamespaceWalker(PythonNamespaceWalker):
    target_namespace = None

    def load_namespaces(self, namespace=None):
        if namespace is None:
            namespace = self.target_namespace
        for _mod in self.walk_namespace(namespace):
            pass

class _classWalker:

    cls_blacklist = frozenset()

    def is_blacklisted(self, cls):
        return cls.__name__ in self.cls_blacklist

    def test_object_derivatives(self, *args, **kwds):
        # first load all namespaces...
        self.load_namespaces()

        # next walk all derivatives of object
        for cls in self.walk_derivatives(object, *args, **kwds):
            if not self._should_ignore(cls):
                self.run_check(cls)

    def iter_builtin_targets(self):
        for attr in dir(__builtins__):
            obj = getattr(__builtins__, attr)
            if not inspect.isclass(obj):
                continue
            yield obj

    def test_builtin_derivatives(self, *args, **kwds):
        self.load_namespaces()
        for obj in self.iter_builtin_targets():
            for cls in self.walk_derivatives(obj, *args, **kwds):
                if not self._should_ignore(cls):
                    self.run_check(cls)

    def walk_derivatives(self, obj):
        raise NotImplementedError(self.__class__, "walk_derivatives")

    def run_check(self, cls):
        raise NotImplementedError


class SubclassWalker(_classWalker):

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


class KlassWalker(_classWalker):

    def walk_derivatives(self, cls, seen=None):
        if cls == type:
            return

        if seen is None:
            seen = set()
        elif cls not in seen:
            seen.add(cls)
            yield cls

        for subcls in cls.__subclasses__():
            if subcls in seen:
                continue
            for node in self.walk_derivatives(subcls, seen=seen):
                yield node
