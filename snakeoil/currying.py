# Copyright: 2005-2011 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""
Function currying, generating a functor with a set of args/defaults pre bound.

:py:func:`pre_curry` and :py:func:`post_curry` return "normal" python functions.
:py:func:`partial` returns a callable object. The difference between
:py:func:`pre_curry` and :py:func:`partial` is this

>>> from snakeoil.currying import pre_curry, partial
>>> def func(arg=None, self=None):
...   return arg, self
>>> curry = pre_curry(func, True)
>>> part = partial(func, True)
>>> class Test(object):
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

If your curried function is not used as a class attribute the results
should be identical. Because :py:func:`partial` has an implementation in c
while :py:func:`pre_curry` is python you should use :py:func:`partial` if possible.
"""

from snakeoil import compatibility
from operator import attrgetter
import sys

__all__ = ("pre_curry", "partial", "post_curry", "pretty_docs",
    "alias_class_method")


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
            return func(*(args+moreargs), **kw)

    callit.func = func
    return callit


class native_partial(object):

    """Like pre_curry, but is a staticmethod by default."""

    def __init__(self, func, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def __call__(self, *moreargs, **morekwargs):
        kw = self.kwargs.copy()
        kw.update(morekwargs)
        return self.func(*(self.args + moreargs), **kw)

# Unused import, unable to import
# pylint: disable-msg=W0611,F0401
try:
    from functools import partial
except ImportError:
    partial = native_partial


def _pydoc_isdata_override(object):
    # yes, import in function is evil.
    # so is this function...
    import inspect
    return not (isinstance(object, partial) or
                inspect.ismodule(object) or inspect.isclass(object) or
                inspect.isroutine(object) or inspect.isframe(object) or
                inspect.istraceback(object) or inspect.iscode(object))


def _inspect_isroutine_override(object):
    import inspect
    return (isinstance(object, partial)
            or inspect.isbuiltin(object)
            or inspect.isfunction(object)
            or inspect.ismethod(object)
            or inspect.ismethoddescriptor(object))


def force_inspect_partial_awareness(only_if_loaded=True):
    if native_partial is not partial:
        if only_if_loaded:
            mod = sys.modules.get('inspect', None)
        else:
            import inspect as mod
        if mod:
            mod.isroutine = _inspect_isroutine_override


def force_pydoc_partial_awareness(only_if_loaded=True):
    # this is probably redundant due to inspect_partial overrides
    # better safe then sorry however.
    if native_partial is not partial:
        if only_if_loaded:
            mod = sys.modules.get('pydoc', None)
        else:
            import pydoc as mod
        if mod:
            mod.isdata = _pydoc_isdata_override


def _epydoc_isroutine_override(object):
    # yes, import in function is evil.
    # so is this function...
    import inspect
    return isinstance(object, partial) or inspect.isroutine(object)


def force_epydoc_partial_awareness(only_if_loaded=True):
    if native_partial is not partial:
        if 'epydoc' in sys.modules or not only_if_loaded:
            import epydoc.docintrospecter as mod
            mod.register_introspecter(_epydoc_isroutine_override,
                mod.introspect_routine, priority=26)


force_inspect_partial_awareness()
force_pydoc_partial_awareness()
force_epydoc_partial_awareness()


def post_curry(func, *args, **kwargs):
    """passed in args are appended to any further args supplied"""

    if not kwargs:
        def callit(*moreargs, **morekwargs):
            return func(*(moreargs+args), **morekwargs)
    elif not args:
        def callit(*moreargs, **morekwargs):
            kw = morekwargs.copy()
            kw.update(kwargs)
            return func(*moreargs, **kw)
    else:
        def callit(*moreargs, **morekwargs):
            kw = morekwargs.copy()
            kw.update(kwargs)
            return func(*(moreargs+args), **kw)

    callit.func = func
    return callit

def pretty_docs(wrapped, extradocs=None, name=None):
    """
    Modify wrapped, so that it 'looks' like what it's wrapping.

    This is primarily useful for introspection reasons- doc generators, direct user
    interaction with an object in the interpretter, etc.

    :param wrapped: functor to modify
    :param extradocs: ``__doc__`` override for wrapped; else it pulls from
        wrapped's target functor
    :param name: ``__name__`` override for wrapped; else it pulls from wrapped's
        target functor for the name.
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


def alias_class_method(attr, name=None, doc=None):
    """at runtime, redirect to another method

    Deprecated.  Use snakeoil.klass.alias_method instead.
    """
    grab_attr = attrgetter(attr)

    def _asecond_level_call(self, *a, **kw):
        return grab_attr(self)(*a, **kw)

    if doc:
        _asecond_level_call.__doc__ = doc
    if name:
        _asecond_level_call.__name__ = name
    return _asecond_level_call


def wrap_exception(recast_exception, *args, **kwds):
    # set this here so that 2to3 will rewrite it.
    try:
        if not issubclass(recast_exception, Exception):
            raise ValueError("recast_exception must be an %s derivative: got %r" %
                (Exception, recast_exception))
    except TypeError, e:
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
    except TypeError, e:
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
        except compatibility.IGNORED_EXCEPTIONS:
            raise
        except ignores:
            raise
        except Exception, e:
            # snag the exception info prior, just to ensure the maker
            # doesn't corrupt the tb info.
            exc_info = sys.exc_info()
            new_exc = exception_maker(e, functor, args, kwargs)
            compatibility.raise_from(new_exc, exc_info=exc_info)
    _wrap_exception.func = functor
    return pretty_docs(_wrap_exception, name=functor.__name__)
