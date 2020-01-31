"""Our unittest extensions."""

__all__ = ('SkipTest', 'TestCase')

from importlib import import_module
import os
import random
import string
import subprocess
import sys
import traceback
import unittest
import warnings

# not relative imports so protect_process() works properly
from snakeoil import fileutils, klass
from snakeoil.compatibility import IGNORED_EXCEPTIONS


def random_str(length):
    """Return a random string of specified length."""
    if sys.hexversion >= 0x03060000:
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    else:
        return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))


def coverage():
    """Extract coverage instance (if it exists) from the current running context."""
    cov = None
    import inspect
    try:
        import coverage
        frame = inspect.currentframe()
        while frame is not None:
            cov = getattr(frame.f_locals.get('self'), 'coverage', None)
            if isinstance(cov, coverage.coverage):
                break
            frame = frame.f_back
    except ImportError:
        pass
    return cov


@klass.patch('os._exit')
def _os_exit(orig_exit, val):
    """Monkeypatch os._exit() to save coverage data before exit."""
    cov = coverage()
    if cov is not None:
        cov.stop()
        cov.save()
    orig_exit(val)


def _tryResultCall(result, methodname, *args):
    method = getattr(result, methodname, None)
    if method is not None:
        if methodname != 'addExpectedFailure':
            method(*args)
            return True
        clsmodule = result.__class__.__module__
        if clsmodule == 'unittest' or clsmodule.startswith("unittest."):
            # bugger...
            method(args[0], args[1])
        else:
            method(args[0], str(args[1][1]), args[2])
        return True
    return None


class SkipTest(Exception):
    """Raise to skip a test."""


def not_a_test(obj):
    """Decorator used to suppress a functor from being treated as a TestCase"""
    obj.__test__ = False
    return obj
not_a_test = not_a_test(not_a_test)


class Todo:

    def __init__(self, reason, errors=None):
        self.reason = reason
        self.errors = errors

    @classmethod
    def parse(cls, todo):
        if isinstance(todo, str):
            return cls(reason=todo)
        errors, reason = todo
        try:
            errors = list(errors)
        except TypeError:
            errors = [errors]
        return cls(reason=reason, errors=errors)

    def expected(self, exception):
        if self.errors is None:
            return True
        for error in self.errors:
            # We want an exact match here.
            if exception is error:
                return True
        return False


class TestCase(unittest.TestCase):

    """Our additions to the standard TestCase.

    This is meant to interact with twisted trial's runner/result objects
    gracefully.

    Extra features:
     - Some extra assert* methods.
     - Support "skip" attributes (strings) on both TestCases and methods.
       Such tests do not run at all under "normal" unittest and get a nice
       "skip" message under trial.
     - Support "todo" attributes (strings, tuples of (ExceptionClass, string)
       or tuples of ((ExceptionClass1, ExceptionClass2, ...), string) on both
       TestCases and methods. Such tests are expected to fail instead of pass.
       If they do succeed that is treated as an error under "normal" unittest.
       If they fail they are ignored under "normal" unittest.
       Under trial both expected failure and unexpected success are reported
       specially.
     - Support "suppress" attributes on methods. They should be a sequence of
       (args, kwargs) tuples suitable for passing to
       :py:func:`warnings.filterwarnings`. The method runs with those additions.
    """

    def __init__(self, methodName='runTest'):
        # This method exists because unittest.py in python 2.4 stores
        # the methodName as __testMethodName while 2.5 uses
        # _testMethodName.
        self._testMethodName = methodName
        unittest.TestCase.__init__(self, methodName)

    def assertLen(self, obj, length, msg=None):
        exp_msg = '%r needs to be len %i, is %i' % (obj, length, len(obj))
        self.assertTrue(len(obj) == length, msg or exp_msg)

    assertInstance = klass.alias_method("assertIsInstance")

    if not hasattr(unittest.TestCase, 'assertIsInstance'):
        def assertIsInstance(self, obj, kls, msg=None):
            """
            assert that obj is an instance of kls
            """
            exp_msg = '%r needs to be an instance of %r, is %r' % (
                obj, kls, getattr(obj, '__class__', "__class__ wasn't pullable"))
            self.assertTrue(isinstance(obj, kls), msg or exp_msg)

    def assertNotInstance(self, obj, kls, msg=None):
        """
        assert that obj is not an instance of kls
        """
        exp_msg = '%r must not be an instance of %r, is %r' % (
            obj, kls, getattr(obj, '__class__', "__class__ wasn't pullable"))
        self.assertFalse(isinstance(obj, kls), msg or exp_msg)

    assertIdentical = klass.alias_method("assertIs")
    if not hasattr(unittest.TestCase, 'assertIs'):
        def assertIs(self, this, other, reason=None):
            self.assertTrue(
                this is other, reason or '%r is not %r' % (this, other))

    def assertNotIdentical(self, this, other, reason=None):
        self.assertTrue(
            this is not other, reason or '%r is %r' % (this, other))

    def assertIn(self, needle, haystack, reason=None):
        self.assertTrue(
            needle in haystack, reason or '%r not in %r' % (needle, haystack))

    def assertNotIn(self, needle, haystack, reason=None):
        self.assertTrue(
            needle not in haystack, reason or '%r in %r' % (needle, haystack))

    def assertEqual(self, obj1, obj2, msg=None, reflective=True):
        self.assertTrue(obj1 == obj2, msg or '%r != %r' % (obj1, obj2))
        if reflective:
            self.assertTrue(not (obj1 != obj2),
                            msg or 'not (%r != %r)' % (obj1, obj2))

    def assertNotEqual(self, obj1, obj2, msg=None, reflective=True):
        self.assertTrue(obj1 != obj2, msg or '%r == %r' % (obj1, obj2))
        if reflective:
            self.assertTrue(not (obj1 == obj2),
                            msg or 'not (%r == %r)' % (obj1, obj2))

    def assertRaises(self, excClass, callableObj, *args, **kwargs):
        try:
            callableObj(*args, **kwargs)
        except excClass:
            return
        except IGNORED_EXCEPTIONS:
            raise
        except Exception as e:
            ex_type, ex, tb = sys.exc_info()

            new_exc = AssertionError(
                "expected an exception of %r type from invocation of-\n"
                "%s(*%r, **%r)\n\ninstead, got the following traceback:\n%s" %
                (excClass, callableObj, args, kwargs, traceback.format_exc()))
            new_exc.__cause__ = e
            new_exc.__traceback__ = tb
            raise new_exc

    def assertRaisesMsg(self, msg, excClass, callableObj, *args, **kwargs):
        """Fail unless an exception of class excClass is thrown
           by callableObj when invoked with arguments args and keyword
           arguments kwargs. If a different type of exception is
           thrown, it will not be caught, and the test case will be
           deemed to have suffered an error, exactly as for an
           unexpected exception.
        """
        try:
            callableObj(*args, **kwargs)
        except excClass:
            return
        else:
            excName = getattr(excClass, '__name__', str(excClass))
            raise self.failureException("%s not raised: %s" % (excName, msg))

    def write_file(self, path, mode, stream, encoding=None):
        return fileutils.write_file(path, mode, stream, encoding=encoding)

    # unittest and twisted each have a differing count of how many frames
    # to pop off when displaying an exception; thus we force an extra
    # frame so that trial results are usable
    @staticmethod
    def forced_extra_frame(test):
        test()

    def run(self, result=None):
        if result is None:
            result = self.defaultTestResult()
        testMethod = getattr(self, self._testMethodName)
        result.startTest(self)
        try:
            skip = getattr(testMethod, 'skip', getattr(self, 'skip', None))
            todo = getattr(testMethod, 'todo', getattr(self, 'todo', None))
            if todo is not None:
                todo = Todo.parse(todo)
            if skip is not None:
                if not _tryResultCall(result, 'addSkip', self, skip):
                    sys.stdout.flush()
                    sys.stdout.write("%s: skipping ... " % skip)
                    sys.stdout.flush()
                    result.addSuccess(self)
                return

            try:
                self.setUp()
            except KeyboardInterrupt:
                raise
            except:
                result.addError(self, sys.exc_info())
                return

            suppressions = getattr(testMethod, 'suppress', ())
            for args, kwargs in suppressions:
                warnings.filterwarnings(*args, **kwargs)
            addedFilters = warnings.filters[:len(suppressions)]
            ok = False
            try:
                try:
                    self.forced_extra_frame(testMethod)
                    ok = True
                except self.failureException:
                    exc = sys.exc_info()
                    if todo is not None and todo.expected(exc[0]):
                        _tryResultCall(result, 'addExpectedFailure',
                                       self, exc, todo)
                    else:
                        result.addFailure(self, exc)
                except SkipTest as e:
                    _tryResultCall(result, 'addSkip', self, str(e))
                except KeyboardInterrupt:
                    raise
                except:
                    exc = sys.exc_info()
                    if todo is not None and todo.expected(exc[0]):
                        _tryResultCall(result, 'addExpectedFailure',
                                       self, exc, todo)
                    else:
                        result.addError(self, exc)
                    # There is a tb in this so do not keep it around.
                    del exc
            finally:
                for filterspec in addedFilters:
                    if filterspec in warnings.filters:
                        warnings.filters.remove(filterspec)

            try:
                self.tearDown()
            except KeyboardInterrupt:
                raise
            except:
                result.addError(self, sys.exc_info())
                ok = False

            if ok:
                if todo is not None:
                    _tryResultCall(result, 'addUnexpectedSuccess', self, todo)
                else:
                    result.addSuccess(self)

        finally:
            result.stopTest(self)


@not_a_test
def mk_cpy_loadable_testcase(extension_namespace, trg_namespace=None,
                             trg_attr=None, src_attr=None):

    class TestCPY_Loaded(TestCase):
        ext_namespace = extension_namespace

        namespace = trg_namespace
        trg_attribute = trg_attr
        src_attribute = src_attr

        def test_it(self):
            dname, bname = self.ext_namespace.rsplit(".", 1)
            dir_mod = import_module(dname)
            fp = os.path.join(os.path.dirname(dir_mod.__file__), '%s.so' % (bname,))
            if not os.path.exists(fp):
                raise SkipTest("for extension %r, path %r doesn't exist" %
                               (self.ext_namespace, fp))
            extension = import_module(self.ext_namespace)
            if self.trg_attribute is None:
                return

            target_scope = import_module(self.namespace)
            ext_obj = extension
            ext_full_name = self.ext_namespace
            if self.src_attribute is not None:
                ext_obj = getattr(ext_obj, self.src_attribute)
                ext_full_name += '.%s' % (self.src_attribute,)

            trg_obj = getattr(target_scope, self.trg_attribute)
            exp_msg = ("expected to find object from %r at '%s.%s', but "
                       "what's there isn't from the extension" %
                       (ext_full_name, self.namespace, self.trg_attribute))
            self.assertIdentical(ext_obj, trg_obj, exp_msg)

    return TestCPY_Loaded


_PROTECT_ENV_VAR = "SNAKEOIL_UNITTEST_PROTECT_PROCESS"


def protect_process(functor, name=None):
    def _inner_run(self, name=name):
        if os.environ.get(_PROTECT_ENV_VAR, False):
            return functor(self)
        if name is None:
            name = "%s.%s.%s" % (self.__class__.__module__, self.__class__.__name__, method_name)
        runner_path = __file__
        if runner_path.endswith(".pyc") or runner_path.endswith(".pyo"):
            runner_path = '%s.py' % (runner_path.rsplit(".")[0],)
        wipe = _PROTECT_ENV_VAR not in os.environ
        try:
            os.environ[_PROTECT_ENV_VAR] = "yes"
            args = [sys.executable, __file__, name]
            p = subprocess.Popen(args, shell=False, env=os.environ.copy(),
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
            stdout, _stderr = p.communicate()
            ret = p.wait()
            assert ret == 0, \
                "subprocess run: %r\nnon zero exit: %s\nstdout:%s\n" % (args, ret, stdout)
        finally:
            if wipe:
                os.environ.pop(_PROTECT_ENV_VAR, None)

    for x in "skip todo __doc__ __name__".split():
        if hasattr(functor, x):
            setattr(_inner_run, x, getattr(functor, x))
    method_name = getattr(functor, '__name__', None)
    return _inner_run
