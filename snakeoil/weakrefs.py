# Copyright: 2006 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

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
