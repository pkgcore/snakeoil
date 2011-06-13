# Copyright: 2006-2010 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""
Object trickery including delayed instantiation and proxying

Note that the delayed instantiation/proxying that is in use here goes several steps
beyond your average proxy implementation- this functionality will take every
step possible to make the proxy appear as if there was _no_ proxy at all.

Specifically this functionality is aware of cpython VM/interpretter semantics-
cpython doesn't use __getattribute__ to pull certain methods (`__str__` is an
example most people are aware of of, `__call__`, `__getitem__`, etc are ones most
aren't).  Delayed instantiation is significantly complicated when these methods
aren't properly handled- you wind up having to pay very close attention to exactly
where those instances are passed to, what access them, do they trigger any of the slotted
special methods, etc.  There is a catch to this however- you can't just define
all slotted methods since if the proxy has those slotted methods, it will use them
and you can't just throw TypeErrors- the execution path has differeed.

Part of the purpose of snakeoil is to make things that should just work, *work*- this
implementation exists to do just that via removing those concerns.  The proxying
knows what the resultant class will be and uses a custom proxy that will appear
the same to the python machinery for slotted methods- literally the python VM
won't try to __iadd__ the proxy unless the resultant class would've supported that
functionality, it will consider it callable if the resultant class would be, etc.

By and large, this proxying is transparent if dealing in python objects (newstyle or old)-
for example,

>>> from snakeoil.obj import DelayedInstantiation_kls
>>> class foo(object):
...   def __init__(self, value):
...     print "instance was created"
...     self.attribute = value
...   pass
>>> delayed = DelayedInstantiation_kls(foo, "bar")
>>> print isinstance(DelayedInstantiation_kls(foo), foo)
True
>>> print delayed.attribute
instance was created
bar

This proxying however cannot cover up certain cpython internal issues- specifically
builtins.

>>> from snakeoil.obj import DelayedInstantiation
>>> delayed_tuple = DelayedInstantiation(tuple, lambda x:tuple(x), xrange(5))
>>> print delayed_tuple + (5, 6, 7)
(0, 1, 2, 3, 4, 5, 6, 7)
>>> print (5, 6, 7) + delayed_tuple
Traceback (most recent call last):
TypeError: can only concatenate tuple (not "CustomDelayedObject") to tuple
>>> # the reason this differs comes down to the cpython vm translating the previous
>>> # call into essentially the following-
>>> print (5, 6, 7).__add__(delayed_tuple)
Traceback (most recent call last):
TypeError: can only concatenate tuple (not "CustomDelayedObject") to tuple

Simply put, while we can emulate/proxy at the python VM layer appearing like the target,
at the c level (which is where tuples are implemented) they expect a certain object
structure, and reach in access it directly in certain cases.  This cannot be safely
proxied (nor realistically can it be proxied in general without extremely horrible
thunking tricks), so it is not attempted.

Essentially, if DelayedInstantiation's/proxies are transparent when dealing in native
python objects- you will not see issues and you don't have to care where those objects
are used, passed to, etc.  If you're trying to proxy a builtin, it's possible, but you
do need to keep an eye on where that instance is passed to since it's not fully transparent.

As demonstrated above, if you're trying to proxy a builtin object, the consuming code
will have to order it's operations appropriately- prefering the proxy's methods
over builtin methods (essentially have the proxy on the left for general ops).

If that doesn't make sense to the reader, it's probably best that the reader not
try to proxy builtin objects like tuples, lists, dicts, sets, etc.
"""

__all__ = ("DelayedInstantiation", "DelayedInstantiation_kls", "make_SlottedDict_kls",
    "make_kls",)

from operator import attrgetter
from snakeoil.currying import pre_curry, pretty_docs
from snakeoil.mappings import DictMixin
from snakeoil import compatibility, klass


# for our proxy, we have two sets of descriptors-
# common, "always there" descriptors that come from
# object itself (this is the base_kls_descriptors sequence)
# and kls_descriptors.  we have a minor optimization in place
# to try and use BaseDelayedObject wherever possible to avoid
# pointless class creation- thus having two seperate lists.

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
    Base proxying object

    This instance specifically has slotted methods matching object's slottings-
    it's basically a base object proxy, defined specifically to avoid having
    to generate a custom class for object derivatives that don't modify slotted
    methods.
    """

    def __new__(cls, desired_kls, func, *a, **kwd):
        """
        :param desired_kls: the class we'll be proxying to
        :param func: a callable to get the actual object

        All other args and keywords are passed to func during instantiation
        """
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
            # special casing for klass.alias_method
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
        locals()[x] = klass.alias_method("__obj__.%s" % (x,),
            doc=getattr(getattr(object, x), '__doc__', None))
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

descriptor_overrides = dict((k, klass.alias_method("__obj__.%s" % (k,)))
    for k in kls_descriptors)

_method_cache = {}
def make_kls(kls, proxy_base=BaseDelayedObject):
    special_descriptors = kls_descriptors.intersection(dir(kls))
    doc = getattr(kls, '__doc__', None)
    if not special_descriptors and doc is None:
        return proxy_base
    key = (tuple(sorted(special_descriptors)), doc)
    o = _method_cache.get(key, None)
    if o is None:
        class CustomDelayedObject(proxy_base):
            locals().update((k, descriptor_overrides[k])
                for k in special_descriptors)
            __doc__ = doc

        o = CustomDelayedObject
        _method_cache[key] = o
    return o

def DelayedInstantiation_kls(kls, *a, **kwd):
    """
    wrapper for DelayedInstantiation

    This just invokes DelayedInstantiation(kls, kls *a, **kwd)

    See :py:func:`DelayedInstantiation` for arguement specifics.
    """
    return DelayedInstantiation(kls, kls, *a, **kwd)

_class_cache = {}
def DelayedInstantiation(resultant_kls, func, *a, **kwd):
    """Generate an objects that does not get initialized before it is used.

    The returned object can be passed around without triggering
    initialization. The first time it is actually used (an attribute
    is accessed) it is initialized once.

    The returned "fake" object cannot completely reliably mimic a
    builtin type. It will usually work but some corner cases may fail
    in confusing ways. Make sure to test if DelayedInstantiation has
    no unwanted side effects.

    :param resultant_kls: type object to fake an instance of.
    :param func: callable, the return value is used as initialized object.

    All other positional args and keywords are passed to func during instantiation.
    """
    o = _class_cache.get(resultant_kls, None)
    if o is None:
        o = make_kls(resultant_kls)
        _class_cache[resultant_kls] = o
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
    """
    Create a space efficient mapping class with a limited set of keys

    Specifically, this function returns a class with it's __slots__ locked
    to the passed in keys- this eliminates the allocation of a dict for the
    instance thus avoiding the wasted memory common to dictionary overallocation-
    for small mappings that waste is roughly 75%, for 100 item mappings it's roughly
    95%, and for 1000 items it's roughly 84%.  Point is, it's sizable, consistantly so.

    The constraint of this is that the resultant mapping has a locked set of
    keys- you cannot add a key that wasn't allowed up front.

    This functionality is primarily useful when you'll be generating many
    dict instances, all with a common set of allowed keys.

    :param keys: iterable/sequence of keys to allow in the resultant mapping

    Example usage:

    >>> from snakeoil.obj import make_SlottedDict_kls
    >>> import sys
    >>> my_kls = make_SlottedDict_kls(["key1", "key2", "key3"])
    >>> items = (("key1", 1), ("key2", 2), ("key3",3))
    >>> inst = dict(items)
    >>> slotted_inst = my_kls(items)
    >>> print sys.getsizeof(inst) # note this is python2.6 functionality
    280
    >>> print sys.getsizeof(slotted_inst)
    72
    >>> # and now for an extreme example:
    >>> raw = dict(("attribute%i" % (x,), x) for x in xrange(1000))
    >>> skls = make_SlottedDict_kls(raw.keys())
    >>> print sys.getsizeof(raw)
    49432
    >>> sraw = skls(raw.iteritems())
    >>> print sys.getsizeof(sraw)
    8048
    >>> print sraw["attribute2"], sraw["attribute3"]
    2 3

    Note that those stats are for a 64bit python 2.6.5 VM.  The stats may
    differ for other python implementations or versions, although for cpython
    the stats above should hold +/- a couple of bites.

    Finally, it's worth noting that the stats above are the minimal savings-
    via a side affect of the __slots__ the keys are automatically interned.

    This means that if you have 100 instances floating around, for dict's
    that costs you sizeof(key) * 100, for slotted dict instances you pay
    sizeof(key) due to the interning.
    """

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
