"""
Function currying, generating a functor with a set of args/defaults pre bound.

:py:func:`pre_curry` and :py:func:`post_curry` return "normal" python functions
The difference between :py:func:`pre_curry` and :py:func:`functools.partial`
is this

>>> from functools import partial
>>> from snakeoil.currying import pre_curry
>>> def func(arg=None, self=None):
...   return arg, self
>>> curry = pre_curry(func, True)
>>> part = partial(func, True)
>>> class Test:
...   curry = pre_curry(func, True)
...   part = partial(func, True)
...   def __repr__(self):
...      return '<Test object>'
>>> curry()
(True, None)
>>> Test().curry()
(True, <Test object>)
>>> part()
(True, None)
>>> Test().part()
(True, None)

If your curried function is not used as a class attribute the results should be
identical. Because :py:func:`functools.partial` has an implementation in C
while :py:func:`pre_curry` is python you should use :py:func:`functools.partial`
if possible.
"""

from functools import partial
import sys

from .compatibility import IGNORED_EXCEPTIONS

__all__ = ("pre_curry", "post_curry", "pretty_docs")


def pre_curry(func, *args, **kwargs):
    """passed in args are prefixed, with further args appended

    Unlike partial, this is usable as an instancemethod.
    """

    if not kwargs:
        def callit(*moreargs, **morekwargs):
            return func(*(args + moreargs), **morekwargs)
    elif not args:
        def callit(*moreargs, **morekwargs):
            kw = kwargs.copy()
            kw.update(morekwargs)
            return func(*moreargs, **kw)
    else:
        def callit(*moreargs, **morekwargs):
            kw = kwargs.copy()
            kw.update(morekwargs)
            return func(*(args + moreargs), **kw)

    callit.func = func
    return callit


def post_curry(func, *args, **kwargs):
    """passed in args are appended to any further args supplied"""

    if not kwargs:
        def callit(*moreargs, **morekwargs):
            return func(*(moreargs + args), **morekwargs)
    elif not args:
        def callit(*moreargs, **morekwargs):
            kw = morekwargs.copy()
            kw.update(kwargs)
            return func(*moreargs, **kw)
    else:
        def callit(*moreargs, **morekwargs):
            kw = morekwargs.copy()
            kw.update(kwargs)
            return func(*(moreargs + args), **kw)

    callit.func = func
    return callit


def pretty_docs(wrapped, extradocs=None, name=None):
    """
    Modify wrapped, so that it 'looks' like what it's wrapping.

    This is primarily useful for introspection reasons- doc generators, direct
    user interaction with an object in the interpretter, etc.

    :param wrapped: functor to modify
    :param extradocs: ``__doc__`` override for wrapped; else it pulls from
        wrapped's target functor
    :param name: ``__name__`` override for wrapped; else it pulls from
        wrapped's target functor for the name.
    """
    wrapped.__module__ = wrapped.func.__module__
    doc = wrapped.func.__doc__
    if extradocs is None:
        wrapped.__doc__ = doc
    else:
        wrapped.__doc__ = extradocs
    if name:
        wrapped.__name__ = name
    return wrapped


def wrap_exception(recast_exception, *args, **kwds):
    # set this here so that 2to3 will rewrite it.
    try:
        if not issubclass(recast_exception, Exception):
            raise ValueError("recast_exception must be an %s derivative: got %r" %
                             (Exception, recast_exception))
    except TypeError as e:
        raise TypeError("recast_exception must be an %s derivative; got %r, failed %r",
                        (Exception.__name__, recast_exception, e))
    ignores = kwds.pop("ignores", (recast_exception,))
    pass_error = kwds.pop("pass_error", None)
    return wrap_exception_complex(partial(_simple_throw, recast_exception, args, kwds, pass_error), ignores)


def _simple_throw(recast_exception, recast_args, recast_kwds, pass_error,
                  exception, functor, args, kwds):
    if pass_error:
        recast_kwds[pass_error] = exception
    return recast_exception(*recast_args, **recast_kwds)


def wrap_exception_complex(creation_func, ignores):
    try:
        if not hasattr(ignores, '__iter__') and issubclass(ignores, Exception) or ignores is Exception:
            ignores = (ignores,)
        ignores = tuple(ignores)
    except TypeError as e:
        raise TypeError("ignores must be either a tuple of %s, or a %s: got %r, error %r"
                        % (Exception.__name__, Exception.__name__, ignores, e))
    if not all(issubclass(x, Exception) for x in ignores):
        raise TypeError("ignores has a non %s derivative in it: %r" %
                        (Exception.__name__, ignores))
    return partial(_inner_wrap_exception, creation_func, ignores)


def _inner_wrap_exception(exception_maker, ignores, functor):
    def _wrap_exception(*args, **kwargs):
        try:
            return functor(*args, **kwargs)
        except IGNORED_EXCEPTIONS:
            raise
        except ignores:
            raise
        except Exception as e:
            raise exception_maker(e, functor, args, kwargs) from e
    _wrap_exception.func = functor
    return pretty_docs(_wrap_exception, name=functor.__name__)
