# Copyright: 2006-2010 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""
Optimized WeakValCache implementation, and a __del__ alternative
"""

__all__ = ("WeakValCache", "WeakRefFinalizer")

# Unused import
# pylint: disable-msg=W0611

try:
    # No name in module
    # pylint: disable-msg=E0611
    from snakeoil._caching import WeakValCache
    from weakref import ref
except ImportError:
    from weakref import WeakValueDictionary as WeakValCache, ref

from snakeoil.obj import make_kls, BaseDelayedObject
from snakeoil.currying import partial
from snakeoil.compatibility import any


def finalize_instance(obj, weakref_inst):
    try:
        obj.__finalizer__()
    finally:
        obj.__disable_finalization__()


class WeakRefProxy(BaseDelayedObject):

    def __instantiate_proxy_instance__(self):
        obj = BaseDelayedObject.__instantiate_proxy_instance__(self)
        weakref = ref(self, partial(finalize_instance, obj))
        obj.__enable_finalization__(weakref)
        return obj

def __enable_finalization__(self, weakref):
    # note we directly access the class, to ensure the instance hasn't overshadowed.
    self.__class__.__finalizer_weakrefs__[id(self)] = weakref

def __disable_finalization__(self):
    # note we directly access the class, to ensure the instance hasn't overshadowed.
    # use pop to allow for repeat invocations of __disable_finalization__
    self.__class__.__finalizer_weakrefs__.pop(id(self), None)


class WeakRefFinalizer(type):

    """
    Metaclass providing __del__ without the gc issues

    While python provides __del__ method support, there are some serious issues
    in their usage- this is detailed at http://docs.python.org/reference/datamodel.html#object.__del__ .

    Summarizing, reference cycles that involve an object that has a
    __del__ method cannot be automatically broken due to the free form
    nature of __del__.  This means __del__ is dodgy to use in practice.

    Weakrefs, by their nature of not strongly ref'ing the target (thus being
    impossible to participate in a reference cycle) are able to invoke finalizers
    upon the target's refcount becoming zero.

    Essentially, what this metaclass does is make it possible to write __del__
    without the issues of __del__; the sole thing you cannot do in __del__ in this
    usage is resurrect the instance.

    This metaclass modifies the target class, renaming it's __del__ to __finalizer__
    and modifying instance generation to return a proxy to the target instance.  This proxy
    is detailed in :mod:`snakeoil.obj`, but suffice it to say it's pretty much
    transparent to all consumers.  When the proxy object is collected, a weakref callback
    fires triggering the proxy targets __finalizer__ method.

    The end result of this trickery is that you can use __del__ w/out the gc issues
    when using this metaclass, and without the specialized hacks required of other
    finalizer implementations.  With this metaclass, you write __del__ as you normally
    would, and have full access to self (rather than a subset of attributes as other
    implementations induce).

    Note that while this makes __del__ possible, it still is recommended to use
    contextmanagers where possible, and alternative approaches that favor a
    deterministics/explicit finalization instead of the implicit finalization that
    __del__ implies.  There however are instances where __del__ is the most elegant
    solution available, thus this metaclass existing.

    Finally, note that the resultant finalization code (the raw `__del__` method)
    is invoked only once on the target instance- attempts to do otherwise via
    invoking __finalizer__() become no-ops.

    Example usage:

    >>> from snakeoil.weakrefs import WeakRefFinalizer
    >>> class foo(object):
    ...   __metaclass__ = WeakRefFinalizer
    ...   def __init__(self, attr):
    ...     self.attr = attr
    ...   def __del__(self):
    ...     print "finalization invoked: %s" % (self.attr,)
    >>>
    >>> obj = foo("bar")
    >>> print obj.__class__.__name__
    foo
    >>> print obj.attr
    bar
    >>> # note that the resultant instance no longer has a __del__
    >>> # method
    >>> print hasattr(obj, '__del__')
    False
    >>> # but it *does* have a __finalizer__ method.
    >>> print hasattr(obj, '__finalizer__')
    True
    >>> del obj
    finalization invoked: bar
    """
    def __new__(cls, name, bases, d):
        if '__del__' in d:
            d['__finalizer__'] = d.pop("__del__")
        elif not '__finalizer__' in d and not \
            any(hasattr(parent, "__finalizer__") for parent in bases):
            raise TypeError("cls %s doesn't have either __del__ nor a __finalizer__"
                % (name,))

        if not '__disable_finalization__' in d and not \
            any(hasattr(parent, "__disable_finalization__") for parent in bases):
            # install tracking
            d['__disable_finalization__'] = __disable_finalization__
            d['__enable_finalization__'] = __enable_finalization__
        # install tracking bits.  we do this per class- this is intended to avoid any
        # potential stupid subclasses wiping a parents tracking.

        d['__finalizer_weakrefs__'] = {}

        new_cls = super(WeakRefFinalizer, cls).__new__(cls, name, bases, d)
        new_cls.__proxy_class__ = partial(make_kls(new_cls, WeakRefProxy), cls, lambda x:x)
        new_cls.__proxy_class__.__name__ = name
        return new_cls

    def __call__(cls, *a, **kw):
        instance = super(WeakRefFinalizer, cls).__call__(*a, **kw)
        proxy = cls.__proxy_class__(instance)
        # force a touch to force instantiation, and
        # weakref registration
        getattr(proxy, '__finalizer__')
        return proxy
