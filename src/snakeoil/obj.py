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
>>> class foo:
...   def __init__(self, value):
...     print("instance was created")
...     self.attribute = value
...   pass
>>> delayed = DelayedInstantiation_kls(foo, "bar")
>>> print(isinstance(DelayedInstantiation_kls(foo), foo))
True
>>> print(delayed.attribute)
instance was created
bar

This proxying however cannot cover up certain cpython internal issues- specifically
builtins.

>>> from snakeoil.obj import DelayedInstantiation
>>> delayed_tuple = DelayedInstantiation(tuple, lambda x: tuple(x), range(5))
>>> print(delayed_tuple + (5, 6, 7))
(0, 1, 2, 3, 4, 5, 6, 7)
>>> print((5, 6, 7) + delayed_tuple)
Traceback (most recent call last):
TypeError: can only concatenate tuple (not "CustomDelayedObject") to tuple
>>> # the reason this differs comes down to the cpython vm translating the previous
>>> # call into essentially the following-
>>> print((5, 6, 7).__add__(delayed_tuple))
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
will have to order its operations appropriately- prefering the proxy's methods
over builtin methods (essentially have the proxy on the left for general ops).

If that doesn't make sense to the reader, it's probably best that the reader not
try to proxy builtin objects like tuples, lists, dicts, sets, etc.
"""



__all__ = ("DelayedInstantiation", "DelayedInstantiation_kls", "make_kls", "popattr")

from . import klass


# For our proxy, we have two sets of descriptors-
# common, "always there" descriptors that come from
# object itself (this is the base_kls_descriptors sequence)
# and kls_descriptors. We have a minor optimization in place
# to try and use BaseDelayedObject wherever possible to avoid
# pointless class creation- thus having two separate lists.

base_kls_descriptors = [
    '__delattr__', '__hash__', '__reduce__',
    '__reduce_ex__', '__repr__', '__setattr__', '__str__',
    '__sizeof__', '__format__', '__subclasshook__',  # >=py2.6
    '__le__', '__lt__', '__ge__', '__gt__', '__eq__', '__ne__',  # py3
    '__dir__',  # >=py3.3
]
base_kls_descriptors = frozenset(base_kls_descriptors)


def popattr(obj, name, default=klass.sentinel):
    """Remove and return an attribute from an object if it exists."""
    try:
        return obj.__dict__.pop(name)
    except KeyError:
        if default is not klass.sentinel:
            return default
        # force AttributeError to be raised
        getattr(obj, name)


class BaseDelayedObject:
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
        locals()[x] = klass.alias_method(
            "__obj__.%s" % (x,),
            doc=getattr(getattr(object, x), '__doc__', None))
    # pylint: disable=undefined-loop-variable
    del x


# note that we ignore __getattribute__; we already handle it.
kls_descriptors = frozenset([
    # rich comparison protocol...
    '__le__', '__lt__', '__eq__', '__ne__', '__gt__', '__ge__',
    # unicode conversion
    '__unicode__',
    # truth...
    '__bool__',
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
    '__call__',
])


kls_descriptors = kls_descriptors.difference(base_kls_descriptors)
descriptor_overrides = {k: klass.alias_method("__obj__.%s" % (k,))
                        for k in kls_descriptors}


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
    r"""Wrapper for DelayedInstantiation

    This just invokes DelayedInstantiation(kls, kls \*a, \*\*kwd)

    See :func:`DelayedInstantiation` for argument specifics.
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
