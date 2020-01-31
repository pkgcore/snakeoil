import pytest

from snakeoil import currying


def passthrough(*args, **kwargs):
    return args, kwargs

# docstring is part of the test

def documented():
    """original docstring"""


class TestPreCurry:

    pre_curry = staticmethod(currying.pre_curry)

    def test_pre_curry(self):
        noop = self.pre_curry(passthrough)
        assert noop() == ((), {})
        assert noop('foo', 'bar') == (('foo', 'bar'), {})
        assert noop(foo='bar') == ((), {'foo': 'bar'})
        assert noop('foo', bar='baz') == (('foo',), {'bar': 'baz'})

        one_arg = self.pre_curry(passthrough, 42)
        assert one_arg() == ((42,), {})
        assert one_arg('foo', 'bar') == ((42, 'foo', 'bar'), {})
        assert one_arg(foo='bar') == ((42,), {'foo': 'bar'})
        assert one_arg('foo', bar='baz') == ((42, 'foo'), {'bar': 'baz'})

        keyword_arg = self.pre_curry(passthrough, foo=42)
        assert keyword_arg() == ((), {'foo': 42})
        assert keyword_arg('foo', 'bar') == (('foo', 'bar'), {'foo': 42})
        assert keyword_arg(foo='bar') == ((), {'foo': 'bar'})
        assert keyword_arg('foo', bar='baz') == (('foo',), {'bar': 'baz', 'foo': 42})

        both = self.pre_curry(passthrough, 42, foo=42)
        assert both() == ((42,), {'foo': 42})
        assert both('foo', 'bar') == ((42, 'foo', 'bar'), {'foo': 42})
        assert both(foo='bar') == ((42,), {'foo': 'bar'})
        assert both('foo', bar='baz') == ((42, 'foo'), {'bar': 'baz', 'foo': 42})

    def test_curry_original(self):
        assert self.pre_curry(passthrough).func is passthrough

    def test_instancemethod(self):
        class Test:
            method = self.pre_curry(passthrough, 'test')
        test = Test()
        assert (('test', test), {}) == test.method()


class Test_pretty_docs:

    currying_targets = (currying.pre_curry, currying.post_curry)

    def test_module_magic(self):
        for target in self.currying_targets:
            assert currying.pretty_docs(target(passthrough)).__module__ is \
                passthrough.__module__
            # test is kinda useless if they are identical without pretty_docs
            assert getattr(target(passthrough), '__module__', None) is not \
                passthrough.__module__

    def test_pretty_docs(self):
        for target in self.currying_targets:
            for func in (passthrough, documented):
                assert currying.pretty_docs(target(func), 'new doc').__doc__ == 'new doc'
                assert currying.pretty_docs(target(func)).__doc__ is func.__doc__


class TestPostCurry:

    def test_post_curry(self):
        noop = currying.post_curry(passthrough)
        assert noop() == ((), {})
        assert noop('foo', 'bar') == (('foo', 'bar'), {})
        assert noop(foo='bar') == ((), {'foo': 'bar'})
        assert noop('foo', bar='baz') == (('foo',), {'bar': 'baz'})

        one_arg = currying.post_curry(passthrough, 42)
        assert one_arg() == ((42,), {})
        assert one_arg('foo', 'bar') == (('foo', 'bar', 42), {})
        assert one_arg(foo='bar') == ((42,), {'foo': 'bar'})
        assert one_arg('foo', bar='baz') == (('foo', 42), {'bar': 'baz'})

        keyword_arg = currying.post_curry(passthrough, foo=42)
        assert keyword_arg() == ((), {'foo': 42})
        assert keyword_arg('foo', 'bar') == (('foo', 'bar'), {'foo': 42})
        assert keyword_arg(foo='bar') == ((), {'foo': 42})
        assert keyword_arg('foo', bar='baz') == (('foo',), {'bar': 'baz', 'foo': 42})

        both = currying.post_curry(passthrough, 42, foo=42)
        assert both() == ((42,), {'foo': 42})
        assert both('foo', 'bar') == (('foo', 'bar', 42), {'foo': 42})
        assert both(foo='bar') == ((42,), {'foo': 42})
        assert both('foo', bar='baz') == (('foo', 42), {'bar': 'baz', 'foo': 42})

    def test_curry_original(self):
        assert currying.post_curry(passthrough).func is passthrough

    def test_instancemethod(self):
        class Test:
            method = currying.post_curry(passthrough, 'test')
        test = Test()
        assert ((test, 'test'), {}) == test.method()


class Test_wrap_exception:

    def test_wrap_exception_complex(self):
        inner, outer = [], []

        inner_exception = ValueError
        wrapping_exception = IndexError

        def f(exception, functor, fargs, fkwds):
            assert isinstance(exception, inner_exception)
            assert functor is throwing_func
            assert fargs == (False,)
            assert fkwds == {'monkey': 'bone'}
            outer.append(True)
            raise wrapping_exception()

        def throwing_func(*args, **kwds):
            assert args == (False,)
            assert kwds == {'monkey': 'bone'}
            inner.append(True)
            raise inner_exception()

        func = currying.wrap_exception_complex(f, IndexError)(throwing_func)

        # basic behaviour
        pytest.raises(IndexError, func, False, monkey='bone')
        assert len(inner) == 1
        assert len(outer) == 1

        # ensure pass thru if it's an allowed exception
        inner_exception = IndexError
        pytest.raises(IndexError, func, False, monkey='bone')
        assert len(inner) == 2
        assert len(outer) == 1

        # finally, ensure it doesn't intercept, and passes thru for
        # exceptions it shouldn't handle
        inner_exception = MemoryError
        pytest.raises(MemoryError, func, False, monkey='bone')
        assert len(inner) == 3
        assert len(outer) == 1

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
        assert func.__name__ == 'throwing_func'
        pytest.raises(ValueError, func)
        throw_kls = IndexError
        pytest.raises(my_exception, func)
        try:
            func()
            raise AssertionError("shouldn't have been able to reach here")
        except my_exception as e:
            assert e.args == (1, 3, 2)
            assert e.kwds == {'monkey': 'bone'}

        # finally, verify that the exception can be pased in.
        func = currying.wrap_exception(
            my_exception, 1, 3, 2, monkey='bone',
            ignores=ValueError, pass_error="the_exception")(throwing_func)
        assert func.__name__ == 'throwing_func'
        pytest.raises(my_exception, func)
        try:
            func()
            raise AssertionError("shouldn't have been able to reach here")
        except my_exception as e:
            assert e.args == (1, 3, 2)
            assert e.kwds == {'monkey': 'bone', 'the_exception': e.__cause__}
