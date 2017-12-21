# Copyright: 2005 Marien Zwart <marienz@gentoo.org>
# License: BSD/GPL2

from snakeoil import currying
from snakeoil.test import TestCase


def passthrough(*args, **kwargs):
    return args, kwargs

# docstring is part of the test

def documented():
    """original docstring"""


class PreCurryTest(TestCase):

    pre_curry = staticmethod(currying.pre_curry)

    def test_pre_curry(self):
        noop = self.pre_curry(passthrough)
        self.assertEqual(noop(), ((), {}))
        self.assertEqual(noop('foo', 'bar'), (('foo', 'bar'), {}))
        self.assertEqual(noop(foo='bar'), ((), {'foo': 'bar'}))
        self.assertEqual(noop('foo', bar='baz'), (('foo',), {'bar': 'baz'}))

        one_arg = self.pre_curry(passthrough, 42)
        self.assertEqual(one_arg(), ((42,), {}))
        self.assertEqual(one_arg('foo', 'bar'), ((42, 'foo', 'bar'), {}))
        self.assertEqual(one_arg(foo='bar'), ((42,), {'foo': 'bar'}))
        self.assertEqual(
            one_arg('foo', bar='baz'), ((42, 'foo'), {'bar': 'baz'}))

        keyword_arg = self.pre_curry(passthrough, foo=42)
        self.assertEqual(keyword_arg(), ((), {'foo': 42}))
        self.assertEqual(
            keyword_arg('foo', 'bar'), (('foo', 'bar'), {'foo': 42}))
        self.assertEqual(keyword_arg(foo='bar'), ((), {'foo': 'bar'}))
        self.assertEqual(
            keyword_arg('foo', bar='baz'),
            (('foo',), {'bar': 'baz', 'foo': 42}))

        both = self.pre_curry(passthrough, 42, foo=42)
        self.assertEqual(both(), ((42,), {'foo': 42}))
        self.assertEqual(
            both('foo', 'bar'), ((42, 'foo', 'bar'), {'foo': 42}))
        self.assertEqual(both(foo='bar'), ((42,), {'foo': 'bar'}))
        self.assertEqual(
            both('foo', bar='baz'), ((42, 'foo'), {'bar': 'baz', 'foo': 42}))

    def test_curry_original(self):
        self.assertIdentical(self.pre_curry(passthrough).func, passthrough)

    def test_instancemethod(self):
        class Test(object):
            method = self.pre_curry(passthrough, 'test')
        test = Test()
        self.assertEqual((('test', test), {}), test.method())


class pretty_docs_Test(TestCase):

    currying_targets = (currying.pre_curry, currying.post_curry)

    def test_module_magic(self):
        for target in self.currying_targets:
            self.assertIdentical(
                currying.pretty_docs(target(passthrough)).__module__,
                passthrough.__module__)
            # test is kinda useless if they are identical without pretty_docs
            self.assertNotIdentical(
                getattr(target(passthrough), '__module__', None),
                passthrough.__module__)

    def test_pretty_docs(self):
        for target in self.currying_targets:
            for func in (passthrough, documented):
                self.assertEqual(
                    currying.pretty_docs(
                        target(func), 'new doc').__doc__,
                    'new doc')
                self.assertIdentical(
                    currying.pretty_docs(target(func)).__doc__,
                    func.__doc__)


class PostCurryTest(TestCase):

    def test_post_curry(self):
        noop = currying.post_curry(passthrough)
        self.assertEqual(noop(), ((), {}))
        self.assertEqual(noop('foo', 'bar'), (('foo', 'bar'), {}))
        self.assertEqual(noop(foo='bar'), ((), {'foo': 'bar'}))
        self.assertEqual(noop('foo', bar='baz'), (('foo',), {'bar': 'baz'}))

        one_arg = currying.post_curry(passthrough, 42)
        self.assertEqual(one_arg(), ((42,), {}))
        self.assertEqual(one_arg('foo', 'bar'), (('foo', 'bar', 42), {}))
        self.assertEqual(one_arg(foo='bar'), ((42,), {'foo': 'bar'}))
        self.assertEqual(
            one_arg('foo', bar='baz'), (('foo', 42), {'bar': 'baz'}))

        keyword_arg = currying.post_curry(passthrough, foo=42)
        self.assertEqual(keyword_arg(), ((), {'foo': 42}))
        self.assertEqual(
            keyword_arg('foo', 'bar'), (('foo', 'bar'), {'foo': 42}))
        self.assertEqual(
            keyword_arg(foo='bar'), ((), {'foo': 42}))
        self.assertEqual(
            keyword_arg('foo', bar='baz'),
            (('foo',), {'bar': 'baz', 'foo': 42}))

        both = currying.post_curry(passthrough, 42, foo=42)
        self.assertEqual(both(), ((42,), {'foo': 42}))
        self.assertEqual(
            both('foo', 'bar'), (('foo', 'bar', 42), {'foo': 42}))
        self.assertEqual(both(foo='bar'), ((42,), {'foo': 42}))
        self.assertEqual(
            both('foo', bar='baz'), (('foo', 42), {'bar': 'baz', 'foo': 42}))

    def test_curry_original(self):
        self.assertIdentical(
            currying.post_curry(passthrough).func, passthrough)

    def test_instancemethod(self):
        class Test(object):
            method = currying.post_curry(passthrough, 'test')
        test = Test()
        self.assertEqual(((test, 'test'), {}), test.method())


class Test_wrap_exception(TestCase):

    def test_wrap_exception_complex(self):
        inner, outer = [], []

        inner_exception = ValueError
        wrapping_exception = IndexError

        def f(exception, functor, fargs, fkwds):
            self.assertIsInstance(exception, inner_exception)
            self.assertIs(functor, throwing_func)
            self.assertEqual(fargs, (False,))
            self.assertEqual(fkwds, {'monkey': 'bone'})
            outer.append(True)
            raise wrapping_exception()

        def throwing_func(*args, **kwds):
            self.assertEqual(args, (False,))
            self.assertEqual(kwds, {'monkey': 'bone'})
            inner.append(True)
            raise inner_exception()

        func = currying.wrap_exception_complex(f, IndexError)(throwing_func)

        # basic behaviour
        self.assertRaises(IndexError, func, False, monkey='bone')
        self.assertLen(inner, 1)
        self.assertLen(outer, 1)

        # ensure pass thru if it's an allowed exception
        inner_exception = IndexError
        self.assertRaises(IndexError, func, False, monkey='bone')
        self.assertLen(inner, 2)
        self.assertLen(outer, 1)

        # finally, ensure it doesn't intercept, and passes thru for
        # exceptions it shouldn't handle
        inner_exception = MemoryError
        self.assertRaises(MemoryError, func, False, monkey='bone')
        self.assertLen(inner, 3)
        self.assertLen(outer, 1)

    def test_wrap_exception(self):
        throw_kls = ValueError

        def throwing_func(*args, **kwds):
            raise throw_kls()

        class my_exception(Exception):
            def __init__(self, *args, **kwds):
                self.args = args
                self.kwds = kwds

        func = currying.wrap_exception(my_exception, 1, 3, 2, monkey='bone',
                                       ignores=ValueError)(throwing_func)
        self.assertEqual(func.__name__, 'throwing_func')
        self.assertRaises(ValueError, func)
        throw_kls = IndexError
        self.assertRaises(my_exception, func)
        try:
            func()
            raise AssertionError("shouldn't have been able to reach here")
        except my_exception as e:
            self.assertEqual(e.args, (1, 3, 2))
            self.assertEqual(e.kwds, {'monkey': 'bone'})

        # finally, verify that the exception can be pased in.
        func = currying.wrap_exception(
            my_exception, 1, 3, 2, monkey='bone',
            ignores=ValueError, pass_error="the_exception")(throwing_func)
        self.assertEqual(func.__name__, 'throwing_func')
        self.assertRaises(my_exception, func)
        try:
            func()
            raise AssertionError("shouldn't have been able to reach here")
        except my_exception as e:
            self.assertEqual(e.args, (1, 3, 2))
            self.assertEqual(e.kwds, {'monkey': 'bone', 'the_exception': e.__cause__})
