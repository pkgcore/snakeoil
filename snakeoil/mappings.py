# Copyright: 2005-2007 Brian Harring <ferringb@gmail.com>
# License: GPL2

"""
miscellanious mapping/dict related classes
"""

import operator
from itertools import imap, chain, ifilterfalse, izip
from snakeoil.klass import get, contains
from collections import deque
from snakeoil import compatibility
cmp = compatibility.cmp

if not compatibility.is_py3k:
    DictMixin_metaclass = type
else:

    class DictMixin_metaclass(type):

        def __new__(cls, name, bases, d):
            if not d.get("disable_py3k_rewriting", False):
                for var in ("keys", "values", "items", "has_key"):
                    d.pop(var, None)
                for var in ("keys", "values", "items"):
                    itervar = 'iter%s' % var
                    if itervar in d:
                        d[var] = d.pop(itervar)
            return type.__new__(cls, name, bases, d)


class DictMixin(object):
    """
    new style class replacement for L{UserDict.DictMixin}
    designed around iter* methods rather then forcing lists as DictMixin does
    """

    __slots__ = ()
    __externally_mutable__ = True
    __metaclass__ = DictMixin_metaclass

    def __init__(self, iterable=None, **kwargs):
        if iterable is not None:
            self.update(iterable)

        if kwargs:
            self.update(kwargs.iteritems())

    def __iter__(self):
        return self.iterkeys()

    def keys(self):
        return list(self.iterkeys())

    def values(self):
        return list(self.itervalues())

    def items(self):
        return list(self.iteritems())

    def has_key(self, key):
        return key in self

    def iterkeys(self):
        raise NotImplementedError(self, "iterkeys")

    def itervalues(self):
        return imap(self.__getitem__, self)

    def iteritems(self):
        for k in self:
            yield k, self[k]

    def update(self, iterable):
        for k, v in iterable:
            self[k] = v

    get = get
    __contains__ = contains

    # default cmp actually operates based on key len comparison, oddly enough
    def __cmp__(self, other):
        for k1, k2 in izip(sorted(self), sorted(other)):
            c = cmp(k1, k2)
            if c != 0:
                return c
            c = cmp(self[k1], other[k2])
            if c != 0:
                return c
        c = cmp(len(self), len(other))
        return c

    def __eq__(self, other):
        return self.__cmp__(other) == 0

    def __ne__(self, other):
        return self.__cmp__(other) != 0

    def pop(self, key, default=None):
        if not self.__externally_mutable__:
            raise AttributeError(self, "pop")
        try:
            val = self[key]
            del self[key]
        except KeyError:
            if default is not None:
                return default
            raise
        return val

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

    def clear(self):
        if not self.__externally_mutable__:
            raise AttributeError(self, "clear")

        # yes, a bit ugly, but this works and is py3k compatible
        # post conversion
        df = self.__delitem__
        for key in self.keys():
            df(key)

    def __len__(self):
        c = 0
        for x in self:
            c += 1
        return c

    def popitem(self):
        if not self.__externally_mutable__:
            raise AttributeError(self, "popitem")
        # do it this way so python handles the stopiteration; faster
        for key, val in self.iteritems():
            del self[key]
            return key, val
        raise KeyError("container is empty")


class LazyValDict(DictMixin):

    """
    Mapping that loads values via a callable

    given a function to get keys, and to look up the val for those keys, it'll
    lazily load key definitions and values as requested
    """
    __slots__ = ("_keys", "_keys_func", "_vals", "_val_func")
    __externally_mutable__ = False

    def __init__(self, get_keys_func, get_val_func):
        """
        @param get_keys_func: either a container, or func to call to get keys.
        @param get_val_func: a callable that is JIT called
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
        return list(self._keys)

    def iterkeys(self):
        if self._keys_func is not None:
            self._keys = set(self._keys_func())
            self._keys_func = None
        return iter(self._keys)

    def itervalues(self):
        return imap(self.__getitem__, self.iterkeys())

    def iteritems(self):
        return ((k, self[k]) for k in self.iterkeys())

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

    """
    Mapping wrapper storing changes to a dict without modifying the original.

    Changes are stored in a secondary dict, protecting the underlying
    mapping from changes.
    """

    __slots__ = ("orig", "new", "blacklist")

    def __init__(self, orig):
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

    def iterkeys(self):
        for k in self.new.iterkeys():
            yield k
        for k in self.orig.iterkeys():
            if k not in self.blacklist and k not in self.new:
                yield k

    def __contains__(self, key):
        return key in self.new or (key not in self.blacklist and
                                   key in self.orig)


class ImmutableDict(dict):

    """Immutable Dict, non changable after instantiating"""

    _hash_key_grabber = operator.itemgetter(0)

    def __delitem__(self, *args):
        raise TypeError("non modifiable")

    __setitem__ = clear = update = pop = popitem = setdefault = __delitem__

    def __hash__(self):
        k = self.items()
        k.sort(key=self._hash_key_grabber)
        return hash(tuple(k))

    __delattr__ = __setitem__
    __setattr__ = __setitem__


class IndeterminantDict(object):

    """A wrapped dict with constant defaults, and a function for other keys."""

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
        raise TypeError("non hashable")

    def __delitem__(self, *args):
        raise TypeError("non modifiable")

    pop = get

    clear = update = popitem = setdefault = __setitem__ = __delitem__
    __iter__ = keys = values = items = __len__ = __delitem__
    iteritems = iterkeys = itervalues = __delitem__


class StackedDict(DictMixin):

    """A non modifiable dict that makes multiple dicts appear as one"""

    def __init__(self, *dicts):
        self._dicts = dicts

    def __getitem__(self, key):
        for x in self._dicts:
            if key in x:
                return x[key]
        raise KeyError(key)

    def iterkeys(self):
        s = set()
        for k in ifilterfalse(s.__contains__, chain(*map(iter, self._dicts))):
            s.add(k)
            yield k

    def __contains__(self, key):
        for x in self._dicts:
            if key in x:
                return True
        return False

    def __setitem__(self, *a):
        raise TypeError("non modifiable")

    __delitem__ = clear = __setitem__


class OrderedDict(DictMixin):

    """Dict that preserves insertion ordering which is used for iteration ops"""

    __slots__ = ("_data", "_order")

    def __init__(self, iterable=()):
        self._order = deque()
        self._data = {}
        for k, v in iterable:
            self[k] = v

    def __setitem__(self, key, val):
        if key not in self:
            self._order.append(key)
        self._data[key] = val

    def __delitem__(self, key):
        del self._data[key]

        for idx, o in enumerate(self._order):
            if o == key:
                del self._order[idx]
                break
        else:
            raise AssertionError("orderdict lost its internal ordering")

    def __getitem__(self, key):
        return self._data[key]

    def __len__(self):
        return len(self._order)

    def iterkeys(self):
        return iter(self._order)

    def clear(self):
        self._order = deque()
        self._data = {}

    def __contains__(self, key):
        return key in self._data


class ListBackedDict(DictMixin):

    __slots__ = ("_data")
    _kls = list
    _key_grabber = operator.itemgetter(0)
    _value_grabber = operator.itemgetter(1)

    def __init__(self, iterables=()):
        self._data = self._kls((k, v) for k, v in iterables)

    def __setitem__(self, key, val):
        for idx, vals in enumerate(self._data):
            if vals[0] == key:
                self._data[idx] = (key, val)
                break
        else:
            self._data.append((key, val))

    def __getitem__(self, key):
        for existing_key, val in self._data:
            if key == existing_key:
                return val
        raise KeyError(key)

    def __delitem__(self, key):
        l = self._kls((k, v) for k, v in self._data if k != key)
        if len(l) == len(self._data):
            # no match.
            raise KeyError(key)
        self._data = l

    def iterkeys(self):
        return imap(self._key_grabber, self._data)

    def itervalues(self):
        return imap(self._value_grabber, self._data)

    def iteritems(self):
        return iter(self._data)

    def __contains__(self, key):
        for k, v in self._data:
            if k == key:
                return True
        return False

    def __len__(self):
        return len(self._data)

class TupleBackedDict(ListBackedDict):
    __slots__ = ()
    _kls = tuple

    def __setitem__(self, key, val):
        self._data = self._kls(
            chain((x for x in self.iteritems() if x[0] != key), ((key, val),)))


class PreservingFoldingDict(DictMixin):

    """dict that uses a 'folder' function when looking up keys.

    The most common use for this is to implement a dict with
    case-insensitive key values (by using C{str.lower} as folder
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
        return PreservingFoldingDict(self._folder, self.iteritems())

    def refold(self, folder=None):
        """Use the remembered original keys to update to a new folder.

        If folder is C{None}, keep the current folding function (this
        is useful if the folding function uses external data and that
        data changed).
        """
        if folder is not None:
            self._folder = folder
        oldDict = self._dict
        self._dict = {}
        for key, value in oldDict.itervalues():
            self._dict[self._folder(key)] = (key, value)

    def __getitem__(self, key):
        return self._dict[self._folder(key)][1]

    def __setitem__(self, key, value):
        self._dict[self._folder(key)] = (key, value)

    def __delitem__(self, key):
        del self._dict[self._folder(key)]

    def iteritems(self):
        return self._dict.itervalues()

    def iterkeys(self):
        for val in self._dict.itervalues():
            yield val[0]

    def itervalues(self):
        for val in self._dict.itervalues():
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
    case-insensitive key values (by using C{str.lower} as folder
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
        return NonPreservingFoldingDict(self._folder, self.iteritems())

    def __getitem__(self, key):
        return self._dict[self._folder(key)]

    def __setitem__(self, key, value):
        self._dict[self._folder(key)] = value

    def __delitem__(self, key):
        del self._dict[self._folder(key)]

    def iterkeys(self):
        return iter(self._dict)

    def itervalues(self):
        return self._dict.itervalues()

    def iteritems(self):
        return self._dict.iteritems()

    def __contains__(self, key):
        return self._folder(key) in self._dict

    def __len__(self):
        return len(self._dict)

    def clear(self):
        self._dict = {}
