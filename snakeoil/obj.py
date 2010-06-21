# Copyright: 2006 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

from operator import attrgetter
from snakeoil.currying import pre_curry
from snakeoil.mappings import DictMixin
from snakeoil import compatibility

def alias_method(getter, self, *a, **kwd):
    return getter(self.__obj__)(*a, **kwd)

# we exempt __getattribute__ since we cover it already, same
# for __new__ and __init__

base_kls_descriptors_compat = []
if compatibility.is_py3k:
    base_kls_descriptors_compat.extend(["__%s__" % x for x in
        ("le", "lt", "ge", "gt", "eq", "ne")])

base_kls_descriptors = frozenset(
    ('__delattr__', '__hash__', '__reduce__',
        '__reduce_ex__', '__repr__', '__setattr__', '__str__'))
if base_kls_descriptors_compat:
    base_kls_descriptors = base_kls_descriptors.union(
        base_kls_descriptors_compat)

if hasattr(object, '__sizeof__'):
    # python 2.6/3.0
    base_kls_descriptors = base_kls_descriptors.union(['__sizeof__',
        '__format__', '__subclasshook__'])


class BaseDelayedObject(object):
    """
    delay actual instantiation
    """

    def __new__(cls, desired_kls, func, *a, **kwd):
        o = object.__new__(cls)
        object.__setattr__(o, "__delayed__", (desired_kls, func, a, kwd))
        object.__setattr__(o, "__obj__", None)
        return o

    def __getattribute__(self, attr):
        obj = object.__getattribute__(self, "__obj__")
        if obj is None:
            if attr == '__class__':
                return object.__getattribute__(self, "__delayed__")[0]
            elif attr == '__doc__':
                kls = object.__getattribute__(self, "__delayed__")[0]
                return getattr(kls, '__doc__', None)

            obj = object.__getattribute__(self, '__instantiate_proxy_instance__')()

        if attr == "__obj__":
            # special casing for alias_method
            return obj
        return getattr(obj, attr)

    def __instantiate_proxy_instance__(self):
        delayed = object.__getattribute__(self, "__delayed__")
        obj = delayed[1](*delayed[2], **delayed[3])
        object.__setattr__(self, "__obj__", obj)
        object.__delattr__(self, "__delayed__")
        return obj

    # special case the normal descriptors
    for x in base_kls_descriptors:
        locals()[x] = pre_curry(alias_method, attrgetter(x))
    del x


# note that we ignore __getattribute__; we already handle it.
kls_descriptors = frozenset([
        # simple comparison protocol...
        '__cmp__',
        # rich comparison protocol...
        '__le__', '__lt__', '__eq__', '__ne__', '__gt__', '__ge__',
        # unicode conversion
        '__unicode__',
        # truth...
        '__nonzero__', '__bool__',
        # container protocol...
        '__len__', '__getitem__', '__setitem__', '__delitem__',
        '__iter__', '__contains__', '__index__', '__reversed__',
        # deprecated sequence protocol bits...
        '__getslice__', '__setslice__', '__delslice__',
        # numeric...
        '__add__', '__sub__', '__mul__', '__floordiv__', '__mod__',
        '__divmod__', '__pow__', '__lshift__', '__rshift__',
        '__and__', '__xor__', '__or__', '__div__', '__truediv__',
        '__rad__', '__rsub__', '__rmul__', '__rdiv__', '__rtruediv__',
        '__rfloordiv__', '__rmod__', '__rdivmod__', '__rpow__',
        '__rlshift__', '__rrshift__', '__rand__', '__rxor__', '__ror__',
        '__iadd__', '__isub__', '__imul__', '__idiv__', '__itruediv__',
        '__ifloordiv__', '__imod__', '__ipow__', '__ilshift__',
        '__irshift__', '__iand__', '__ixor__', '__ior__',
        '__neg__', '__pos__', '__abs__', '__invert__', '__complex__',
        '__int__', '__long__', '__float__', '__oct__', '__hex__',
        '__coerce__', '__trunc__', '__radd__', '__floor__', '__ceil__',
        '__round__',
        # remaining...
        '__call__'])

if base_kls_descriptors_compat:
    kls_descriptors = kls_descriptors.difference(base_kls_descriptors_compat)

descriptor_overrides = dict((k, pre_curry(alias_method, attrgetter(k)))
    for k in kls_descriptors)

method_cache = {}
def make_kls(kls, proxy_base=BaseDelayedObject):
    special_descriptors = kls_descriptors.intersection(dir(kls))
    doc = getattr(kls, '__doc__', None)
    if not special_descriptors or doc is None:
        return proxy_base
    key = (tuple(sorted(special_descriptors)), doc)
    o = method_cache.get(key, None)
    if o is None:
        class CustomDelayedObject(proxy_base):
            locals().update((k, descriptor_overrides[k])
                for k in special_descriptors)
            __doc__ = doc

        o = CustomDelayedObject
        method_cache[key] = o
    return o

def DelayedInstantiation_kls(kls, *a, **kwd):
    return DelayedInstantiation(kls, kls, *a, **kwd)

class_cache = {}
def DelayedInstantiation(resultant_kls, func, *a, **kwd):
    """Generate an objects that does not get initialized before it is used.

    The returned object can be passed around without triggering
    initialization. The first time it is actually used (an attribute
    is accessed) it is initialized once.

    The returned "fake" object cannot completely reliably mimic a
    builtin type. It will usually work but some corner cases may fail
    in confusing ways. Make sure to test if DelayedInstantiation has
    no unwanted side effects.

    @param resultant_kls: type object to fake an instance of.
    @param func: callable, the return value is used as initialized object.
    """
    o = class_cache.get(resultant_kls, None)
    if o is None:
        o = make_kls(resultant_kls)
        class_cache[resultant_kls] = o
    return o(resultant_kls, func, *a, **kwd)


def native_attr_getitem(self, key):
    try:
        return getattr(self, key)
    except AttributeError:
        raise KeyError(key)

def native_attr_update(self, iterable):
    for k, v in iterable:
        setattr(self, k, v)

def native_attr_contains(self, key):
     return hasattr(self, key)

def native_attr_delitem(self, key):
     # Python does not raise anything if you delattr an
     # unset slot (works ok if __slots__ is not involved).
     try:
         getattr(self, key)
     except AttributeError:
         raise KeyError(key)
     delattr(self, key)

def native_attr_pop(self, key, *a):
    # faster then the exception form...
    l = len(a)
    if l > 1:
        raise TypeError("pop accepts 1 or 2 args only")
    if hasattr(self, key):
        o = getattr(self, key)
        object.__delattr__(self, key)
    elif l:
        o = a[0]
    else:
        raise KeyError(key)
    return o

def native_attr_get(self, key, default=None):
    return getattr(self, key, default)

try:
    from snakeoil._klass import (attr_getitem, attr_setitem, attr_delitem,
        attr_update, attr_contains, attr_pop, attr_get)
except ImportError:
    attr_getitem = native_attr_getitem
    attr_setitem = object.__setattr__
    attr_delitem = native_attr_delitem
    attr_update = native_attr_update
    attr_contains = native_attr_contains
    attr_pop = native_attr_pop
    attr_get = native_attr_get

slotted_dict_cache = {}
def make_SlottedDict_kls(keys):
    new_keys = tuple(sorted(keys))
    o = slotted_dict_cache.get(new_keys, None)
    if o is None:
        class SlottedDict(DictMixin):
            __slots__ = new_keys
            __externally_mutable__ = True

            def __init__(self, iterables=()):
                if iterables:
                    self.update(iterables)

            __setitem__ = attr_setitem
            __getitem__ = attr_getitem
            __delitem__ = attr_delitem
            __contains__ = attr_contains
            update = attr_update
            pop = attr_pop
            get = attr_get

            def __iter__(self):
                for k in self.__slots__:
                    if hasattr(self, k):
                        yield k

            def iterkeys(self):
                return iter(self)

            def itervalues(self):
                for k in self:
                    yield self[k]

            def clear(self):
                for k in self:
                    del self[k]

            def __len__(self):
                return len(self.keys())


        o = SlottedDict
        slotted_dict_cache[new_keys] = o
    return o
