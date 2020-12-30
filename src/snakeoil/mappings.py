"""
Miscellaneous mapping related classes and functionality
"""

__all__ = (
    "DictMixin", "LazyValDict", "LazyFullValLoadDict",
    "ProtectedDict", "ImmutableDict", "IndeterminantDict",
    "defaultdictkey", "AttrAccessible", "StackedDict",
    "make_SlottedDict_kls", "ProxiedAttrs",
)

from collections import defaultdict
from collections.abc import Mapping, MutableSet, Set
from functools import partial
from itertools import chain, filterfalse, islice
import operator

from .klass import get, contains, steal_docs, sentinel


class DictMixin:
    """
    new style class replacement for :py:func:`UserDict.DictMixin`
    designed around iter* methods rather then forcing lists as DictMixin does

    To use this mixin, you need to define the following methods:

    * __delitem__
    * __setitem__
    * __getitem__
    * keys

    It's suggested for performance reasons, it might be worth defining
    `values` and `items` in addition.
    """

    __slots__ = ()
    __externally_mutable__ = True

    def __init__(self, iterable=None, **kwargs):
        """
        :param iterables: optional, an iterable of (key, value) to initialize this
            instance with
        :param kwargs: optional, key=value form of specifying the keys value tuples to
            store in this instance.
        """
        if iterable is not None:
            self.update(iterable)

        if kwargs:
            self.update(kwargs.items())

    @steal_docs(dict)
    def __iter__(self):
        return self.keys()

    @steal_docs(dict)
    def __str__(self):
        return str(dict(self.items()))

    @steal_docs(dict)
    def items(self):
        for k in self:
            yield k, self[k]

    @steal_docs(dict)
    def keys(self):
        raise NotImplementedError(self, "keys")

    @steal_docs(dict)
    def values(self):
        return map(self.__getitem__, self)

    @steal_docs(dict)
    def update(self, iterable):
        for k, v in iterable:
            self[k] = v

    get = get
    __contains__ = contains

    @steal_docs(dict)
    def __eq__(self, other):
        if len(self) != len(other):
            return False
        for k1, k2 in zip(sorted(self), sorted(other)):
            if k1 != k2:
                return False
            if self[k1] != other[k2]:
                return False
        return True

    @steal_docs(dict)
    def __ne__(self, other):
        return not self.__eq__(other)

    @steal_docs(dict)
    def pop(self, key, default=sentinel):
        if not self.__externally_mutable__:
            raise AttributeError(self, "pop")
        try:
            val = self[key]
            del self[key]
        except KeyError:
            if default is not sentinel:
                return default
            raise
        return val

    @steal_docs(dict)
    def setdefault(self, key, default=None):
        if not self.__externally_mutable__:
            raise AttributeError(self, "setdefault")
        if key in self:
            return self[key]
        self[key] = default
        return default

    def __getitem__(self, key):
        raise NotImplementedError(self, "__getitem__")

    def __setitem__(self, key, val):
        if not self.__externally_mutable__:
            raise AttributeError(self, "__setitem__")
        raise NotImplementedError(self, "__setitem__")

    def __delitem__(self, key):
        if not self.__externally_mutable__:
            raise AttributeError(self, "__delitem__")
        raise NotImplementedError(self, "__delitem__")

    @steal_docs(dict)
    def clear(self):
        if not self.__externally_mutable__:
            raise AttributeError(self, "clear")

        # yes, a bit ugly, but this works and is py3k compatible
        # post conversion
        df = self.__delitem__
        for key in list(self.keys()):
            df(key)

    def __len__(self):
        c = 0
        for _ in self:
            c += 1
        return c

    def __bool__(self):
        for _ in self:
            return True
        return False

    @steal_docs(dict)
    def popitem(self):
        if not self.__externally_mutable__:
            raise AttributeError(self, "popitem")
        # do it this way so python handles the stopiteration; faster
        for key, val in self.items():
            del self[key]
            return key, val
        raise KeyError("container is empty")


class LazyValDict(DictMixin):
    """Mapping that loads values via a callable.

    given a function to get keys, and to look up the val for those keys, it'll
    lazily load key definitions and values as requested
    """
    __slots__ = ("_keys", "_keys_func", "_vals", "_val_func")
    __externally_mutable__ = False

    def __init__(self, get_keys_func, get_val_func):
        """
        :param get_keys_func: either a container, or func to call to get keys.
        :param get_val_func: a callable that is JIT called
            with the key requested.
        """
        if not callable(get_val_func):
            raise TypeError("get_val_func isn't a callable")
        if hasattr(get_keys_func, "__iter__"):
            self._keys = get_keys_func
            self._keys_func = None
        else:
            if not callable(get_keys_func):
                raise TypeError(
                    "get_keys_func isn't iterable or callable")
            self._keys_func = get_keys_func
        self._val_func = get_val_func
        self._vals = {}

    def __getitem__(self, key):
        if self._keys_func is not None:
            self._keys = set(self._keys_func())
            self._keys_func = None
        if key in self._vals:
            return self._vals[key]
        if key in self._keys:
            v = self._vals[key] = self._val_func(key)
            return v
        raise KeyError(key)

    def keys(self):
        if self._keys_func is not None:
            self._keys = set(self._keys_func())
            self._keys_func = None
        return iter(self._keys)

    def values(self):
        return map(self.__getitem__, self.keys())

    def items(self):
        return ((k, self[k]) for k in self.keys())

    def __contains__(self, key):
        if self._keys_func is not None:
            self._keys = set(self._keys_func())
            self._keys_func = None
        return key in self._keys

    def __len__(self):
        if self._keys_func is not None:
            self._keys = set(self._keys_func())
            self._keys_func = None
        return len(self._keys)


class LazyFullValLoadDict(LazyValDict):
    """Lazily load all keys for this mapping in a single load.

    This is essentially the same thing as :py:class:`LazyValDict`, just that the
    load function must return all keys in a single request.

    The val function must still return values one by one per key.
    """
    __slots__ = ()

    def __getitem__(self, key):
        if self._keys_func is not None:
            self._keys = set(self._keys_func())
            self._keys_func = None
        if key in self._vals:
            return self._vals[key]
        if key in self._keys:
            if self._val_func is not None:
                self._vals.update(self._val_func(self._keys))
                return self._vals[key]
        raise KeyError(key)


class ProtectedDict(DictMixin):
    """Mapping wrapper storing changes to a dict without modifying the original.

    Changes are stored in a secondary dict, protecting the underlying
    mapping from changes.
    """

    __slots__ = ("orig", "new", "blacklist")

    def __init__(self, orig):
        """
        :param orig: original dictionary to wrap
        """
        self.orig = orig
        self.new = {}
        self.blacklist = {}

    def __setitem__(self, key, val):
        self.new[key] = val
        if key in self.blacklist:
            del self.blacklist[key]

    def __getitem__(self, key):
        if key in self.new:
            return self.new[key]
        if key in self.blacklist:
            raise KeyError(key)
        return self.orig[key]

    def __delitem__(self, key):
        if key in self.new:
            del self.new[key]
            self.blacklist[key] = True
            return
        elif key in self.orig:
            if key not in self.blacklist:
                self.blacklist[key] = True
                return
        raise KeyError(key)

    def keys(self):
        for k in self.new.keys():
            yield k
        for k in self.orig.keys():
            if k not in self.blacklist and k not in self.new:
                yield k

    def __contains__(self, key):
        return key in self.new or (key not in self.blacklist and
                                   key in self.orig)


class ImmutableDict(Mapping):
    """Immutable dict, unchangeable after instantiating.

    Because this is immutable, it's hashable.
    """

    def __init__(self, data=None):
        if isinstance(data, ImmutableDict):
            mapping = data._dict
        elif isinstance(data, Mapping):
            mapping = data
        elif isinstance(data, DictMixin):
            mapping = {k: v for k, v in data.items()}
        elif data is None:
            mapping = {}
        else:
            try:
                mapping = {k: v for k, v in data}
            except TypeError as e:
                raise TypeError(f'unsupported data format: {e}')
        object.__setattr__(self, '_dict', mapping)

    def __getitem__(self, key):
        # hack to avoid recursion exceptions for subclasses that use
        # inject_getitem_as_getattr()
        if key == '_dict':
            return object.__getattribute__(self, '_dict')
        return self._dict[key]

    def __iter__(self):
        return iter(self._dict)

    def __reversed__(self):
        return reversed(self._dict)

    def __len__(self):
        return len(self._dict)

    def __repr__(self):
        return str(self._dict)

    def __str__(self):
        return str(self._dict)

    def __hash__(self):
        return hash(tuple(sorted(self._dict.items(), key=operator.itemgetter(0))))


class OrderedFrozenSet(Set):
    """Ordered, immutable set using guaranteed insertion order dicts in py3.6 onwards."""

    def __init__(self, iterable=()):
        try:
            self._dict = ImmutableDict({x: None for x in iterable})
        except TypeError as e:
            raise TypeError('not iterable') from e

    def __contains__(self, key):
        return key in self._dict

    def __iter__(self):
        return iter(self._dict)

    def __getitem__(self, key):
        try:
            return next(islice(self._dict, key, None))
        except StopIteration:
            raise IndexError('index out of range')

    def __reversed__(self):
        return reversed(self._dict)

    def __len__(self):
        return len(self._dict)

    def __eq__(self, other):
        return set(self._dict) == other

    def __str__(self):
        elements_str = ', '.join(map(repr, self._dict))
        return f'{{{elements_str}}}'

    def __repr__(self):
        return self.__str__()

    def __hash__(self):
        return hash(self._dict)

    def intersection(self, other):
        return self.__class__(self._dict.keys() & other)

    def union(self, other):
        return self.__class__(self._dict.keys() | other)

    def difference(self, other):
        return self.__class__(self._dict.keys() - other)

    def symmetric_difference(self, other):
        return self.__class__(self._dict.keys() ^ other)


class OrderedSet(OrderedFrozenSet, MutableSet):
    """Ordered, mutable set using guaranteed insertion order dicts in py3.6 onwards."""

    def __init__(self, iterable=()):
        try:
            self._dict = {x: None for x in iterable}
        except TypeError as e:
            raise TypeError('not iterable') from e

    def add(self, value):
        self._dict[value] = None

    def discard(self, value):
        try:
            del self._dict[value]
        except KeyError:
            pass

    def remove(self, value):
        del self._dict[value]

    def clear(self):
        self._dict = {}

    def update(self, iterable):
        self._dict.update((x, None) for x in iterable)

    def __hash__(self):
        raise TypeError(f'unhashable type: {self.__class__.__name__!r}')


class IndeterminantDict:
    """A wrapped dict with constant defaults, and a function for other keys.

    The primary use for this class is to make a JIT loaded mapping- for instance, a
    mapping representing the filesystem that loads keys/values as it goes.
    """

    __slots__ = ("__initial", "__pull")

    def __init__(self, pull_func, starter_dict=None):
        object.__init__(self)
        if starter_dict is None:
            self.__initial = {}
        else:
            self.__initial = starter_dict
        self.__pull = pull_func

    def __getitem__(self, key):
        if key in self.__initial:
            return self.__initial[key]
        else:
            return self.__pull(key)

    def get(self, key, val=None):
        try:
            return self[key]
        except KeyError:
            return val

    def __hash__(self):
        raise TypeError("unhashable")

    pop = get

    def __unmodifiable(func, *args):
        raise TypeError(f"indeterminate dict: '{func}()' can't modify {args!r}")
    for func in ('__delitem__', '__setitem__', 'setdefault', 'popitem', 'update', 'clear'):
        locals()[func] = partial(__unmodifiable, func)

    def __indeterminate(func, *args):
        raise TypeError(f"indeterminate dict: '{func}()' is inaccessible")
    for func in ('__iter__', '__len__', 'keys', 'values', 'items'):
        locals()[func] = partial(__indeterminate, func)


class StackedDict(DictMixin):
    """An unmodifiable dict that makes multiple dicts appear as one"""

    def __init__(self, *dicts):
        self._dicts = dicts

    def __getitem__(self, key):
        for x in self._dicts:
            if key in x:
                return x[key]
        raise KeyError(key)

    def keys(self):
        s = set()
        for k in filterfalse(s.__contains__, chain(*self._dicts)):
            s.add(k)
            yield k

    def __contains__(self, key):
        for x in self._dicts:
            if key in x:
                return True
        return False

    def __setitem__(self, *a):
        raise TypeError("unmodifiable")

    __delitem__ = clear = __setitem__


class PreservingFoldingDict(DictMixin):
    """dict that uses a 'folder' function when looking up keys.

    The most common use for this is to implement a dict with
    case-insensitive key values (by using ``str.lower`` as folder
    function).

    This version returns the original 'unfolded' key.
    """

    def __init__(self, folder, sourcedict=None):
        self._folder = folder
        # dict mapping folded keys to (original key, value)
        self._dict = {}
        if sourcedict is not None:
            self.update(sourcedict)

    def copy(self):
        return PreservingFoldingDict(self._folder, iter(self.items()))

    def refold(self, folder=None):
        """Use the remembered original keys to update to a new folder.

        If folder is None, keep the current folding function (this
        is useful if the folding function uses external data and that
        data changed).
        """
        if folder is not None:
            self._folder = folder
        oldDict = self._dict
        self._dict = {}
        for key, value in oldDict.values():
            self._dict[self._folder(key)] = (key, value)

    def __getitem__(self, key):
        return self._dict[self._folder(key)][1]

    def __setitem__(self, key, value):
        self._dict[self._folder(key)] = (key, value)

    def __delitem__(self, key):
        del self._dict[self._folder(key)]

    def items(self):
        return iter(self._dict.values())

    def keys(self):
        for val in self._dict.values():
            yield val[0]

    def values(self):
        for val in self._dict.values():
            yield val[1]

    def __contains__(self, key):
        return self._folder(key) in self._dict

    def __len__(self):
        return len(self._dict)

    def clear(self):
        self._dict = {}


class NonPreservingFoldingDict(DictMixin):
    """dict that uses a 'folder' function when looking up keys.

    The most common use for this is to implement a dict with
    case-insensitive key values (by using ``str.lower`` as folder
    function).

    This version returns the 'folded' key.
    """

    def __init__(self, folder, sourcedict=None):
        self._folder = folder
        # dict mapping folded keys to values.
        self._dict = {}
        if sourcedict is not None:
            self.update(sourcedict)

    def copy(self):
        return NonPreservingFoldingDict(self._folder, iter(self.items()))

    def __getitem__(self, key):
        return self._dict[self._folder(key)]

    def __setitem__(self, key, value):
        self._dict[self._folder(key)] = value

    def __delitem__(self, key):
        del self._dict[self._folder(key)]

    def keys(self):
        return iter(self._dict.keys())

    def values(self):
        return iter(self._dict.values())

    def items(self):
        return iter(self._dict.items())

    def __contains__(self, key):
        return self._folder(key) in self._dict

    def __len__(self):
        return len(self._dict)

    def clear(self):
        self._dict = {}


class defaultdictkey(defaultdict):
    """:py:class:`defaultdict` derivative that automatically stores any missing key/value pairs.

    Specifically, if instance[missing_key] is accessed, the `__missing__` method automatically
    store self[missing_key] = self.default_factory(key).
    """
    def __init__(self, default_factory):
        # we have our own init to explicitly force via prototype
        # that a default_factory is required
        defaultdict.__init__(self, default_factory)

    @steal_docs(defaultdict)
    def __missing__(self, key):
        obj = self[key] = self.default_factory(key)
        return obj


def _KeyError_to_Attr(functor):
    def inner(self, *args):
        try:
            return functor(self, *args)
        except KeyError:
            raise AttributeError(args[0])
    inner.__name__ = functor.__name__
    inner.__doc__ = functor.__doc__
    return inner


def inject_getitem_as_getattr(scope):
    """Modify a given class scope proxying attr access to dict access.

    If the given scope already has __getattr__, __setattr__, or __delattr__,
    the pre-existing method will not be overridden.

    Example usage:

    >>> class my_options(dict):
    ...    inject_getitem_as_getattr(locals())
    >>>
    >>> d = my_options(asdf=1)
    >>> print(d.asdf)
    1
    >>> d.asdf = 2
    >>> print(d.asdf)
    2
    >>> del d.asdf
    >>> print('asdf' in d)
    False
    >>> print(hasattr(d, 'asdf'))
    False

    :param scope: the scope of a class to modify, adding methods as needed
    """

    scope.setdefault('__getattr__', _KeyError_to_Attr(operator.__getitem__))
    scope.setdefault('__delattr__', _KeyError_to_Attr(operator.__delitem__))
    scope.setdefault('__setattr__', _KeyError_to_Attr(operator.__setitem__))


class AttrAccessible(dict):
    """Simple dict class allowing instance.x and instance['x'] access."""

    __slots__ = ()

    inject_getitem_as_getattr(locals())


class ProxiedAttrs(DictMixin):
    """Proxy mapping protocol to an object's attributes.

    Example usage:

    >>> class foo:
    ...     pass
    >>> obj = foo()
    >>> obj.x, obj.y = 1, 2
    >>> d = ProxiedAttrs(obj)
    >>> print(d['x'])
    1
    >>> del d['x']
    >>> print(hasattr(obj, 'x'))
    False

    :param target: The object to wrap.
    """

    __slots__ = ('__target__',)

    def __init__(self, target):
        self.__target__ = target

    def __getitem__(self, key):
        try:
            return getattr(self.__target__, key)
        except AttributeError:
            raise KeyError(key)

    def __setitem__(self, key, value):
        try:
            return setattr(self.__target__, key, value)
        except AttributeError:
            raise KeyError(key)

    def __delitem__(self, key):
        try:
            return delattr(self.__target__, key)
        except AttributeError:
            raise KeyError(key)

    def keys(self):
        return iter(dir(self.__target__))


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


# python issue 7604; depending on the python version, delattr'ing an empty slot
# doesn't throw AttributeError; we vary our implementation for efficiency
# dependent on a onetime runtime test of that.
class foo:
    __slots__ = ("slot",)

# track which is required since if we can use extensions, we'll have
# to choose which to import; cpy side exports both, leaving it to us
# to decide which to use (via runtime check, it means we don't have to
# be recompiled for minor bumps when the fix is in place- it just switches
# on).
_use_slow_delitem = True
try:
    del foo().slot
except AttributeError:
    # properly throws an exception; thus we do a single lookup.
    _use_slow_delitem = False

    def native_attr_delitem(self, key):
        try:
            delattr(self, key)
        except AttributeError:
            raise KeyError(key)
else:
    # doesn't throw the exception; double lookup, getattr, than delattr.
    def native_attr_delitem(self, key):
        # Python does not raise anything if you delattr an
        # unset slot (works ok if __slots__ is not involved).
        try:
            getattr(self, key)
        except AttributeError:
            raise KeyError(key)
        delattr(self, key)

# cleanup the test class.
del foo


def native_attr_pop(self, key, *a):
    # faster then the exception form...
    l = len(a)
    if l > 1:
        raise TypeError("pop accepts 1 or 2 args only")
    o = getattr(self, key, sentinel)
    if o is not sentinel:
        object.__delattr__(self, key)
    elif l:
        o = a[0]
    else:
        raise KeyError(key)
    return o


def native_attr_get(self, key, default=None):
    return getattr(self, key, default)

try:
    from ._klass import (
        attr_getitem, attr_setitem, attr_update, attr_contains, attr_pop, attr_get)
    if _use_slow_delitem:
        from ._klass import attr_delitem_slow as attr_delitem
    else:
        from ._klass import attr_delitem_fast as attr_delitem
except ImportError:
    attr_getitem = native_attr_getitem
    attr_setitem = object.__setattr__
    attr_delitem = native_attr_delitem
    attr_update = native_attr_update
    attr_contains = native_attr_contains
    attr_pop = native_attr_pop
    attr_get = native_attr_get


class _SlottedDict(DictMixin):
    """A space efficient mapping class with a limited set of keys.

    Specifically, this class has its __slots__ locked to the passed in keys-
    this eliminates the allocation of a dict for the instance thus avoiding the
    wasted memory common to dictionary overallocation- for small mappings that
    waste is roughly 75%, for 100 item mappings it's roughly 95%, and for 1000
    items it's roughly 84%.  Point is, it's sizable, consistantly so.

    The constraint of this is that the resultant mapping has a locked set of
    keys- you cannot add a key that wasn't allowed up front.

    This functionality is primarily useful when you'll be generating many
    dict instances, all with a common set of allowed keys.

    :param keys: iterable/sequence of keys to allow in the resultant mapping

    Example usage:

    >>> from snakeoil.mappings import make_SlottedDict_kls
    >>> import sys
    >>> my_kls = make_SlottedDict_kls(["key1", "key2", "key3"])
    >>> items = (("key1", 1), ("key2", 2), ("key3",3))
    >>> inst = dict(items)
    >>> slotted_inst = my_kls(items)
    >>> print(sys.getsizeof(inst))
    280
    >>> print(sys.getsizeof(slotted_inst))
    72
    >>> # and now for an extreme example:
    >>> raw = {"attribute%i" % (x,): x for x in range(1000)}
    >>> skls = make_SlottedDict_kls(raw.keys())
    >>> print(sys.getsizeof(raw))
    49432
    >>> sraw = skls(raw.items())
    >>> print(sys.getsizeof(sraw))
    8048
    >>> print(sraw["attribute2"], sraw["attribute3"])
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

    __slots__ = ()
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

    def keys(self):
        return iter(self)

    def values(self):
        for k in self:
            yield self[k]

    def clear(self):
        for k in self:
            del self[k]

    def __len__(self):
        return len(list(self.keys()))


def make_SlottedDict_kls(keys):
    """Create a space efficient mapping class with a limited set of keys."""
    new_keys = tuple(sorted(keys))
    cls_name = f'SlottedDict_{hash(new_keys)}'
    o = globals().get(cls_name, None)
    if o is None:
        o = type(cls_name, (_SlottedDict,), {})
        o.__slots__ = new_keys
        globals()[cls_name] = o
    return o
