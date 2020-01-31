"""
Container classes and functionality for implementing them

"""

__all__ = (
    "InvertedContains", "SetMixin", "LimitedChangeSet", "Unchangable",
    "ProtectedSet", "RefCountingSet"
)

from itertools import chain, filterfalse

from .klass import steal_docs


class InvertedContains(set):

    """Set that inverts all contains lookup results.

    Essentially, it's a set class usable for blacklist containment testing.

    >>> from snakeoil.containers import InvertedContains
    >>> inverted = InvertedContains(range(10))
    >>> assert 1 not in inverted
    >>> assert 11 in inverted
    >>> inverted.add(11)
    >>> assert 11 not in inverted

    Please note it cannot be iterated over due to the essentially
    infinite series it represents.
    """

    def __contains__(self, key):
        return not set.__contains__(self, key)

    def __iter__(self):
        # infinite set, non iterable.
        raise TypeError("InvertedContains cannot be iterated over")


class SetMixin:
    """
    Base class for implementing set classes

    Subclasses must provide __init__, __iter__ and __contains__.

    Note that this is a stripped down base; it primarily implements the core
    math protocols, methods like symmetric_difference aren't defined here.

    """

    @steal_docs(set)
    def __and__(self, other, kls=None):
        # Note: for these methods we don't bother to filter dupes from this
        # list -  since the subclasses __init__ should already handle this,
        # there's no point doing it twice.
        return (kls or self.__class__)(x for x in self if x in other)

    @steal_docs(set)
    def __rand__(self, other):
        return self.__and__(other, kls=other.__class__)

    @steal_docs(set)
    def __or__(self, other, kls=None):
        return (kls or self.__class__)(chain(self, other))

    @steal_docs(set)
    def __ror__(self, other):
        return self.__or__(other, kls=other.__class__)

    @steal_docs(set)
    def __xor__(self, other, kls=None):
        return (kls or self.__class__)(chain(
            (x for x in self if x not in other),
            (x for x in other if x not in self)))

    @steal_docs(set)
    def __rxor__(self, other):
        return self.__xor__(other, kls=other.__class__)

    @steal_docs(set)
    def __sub__(self, other):
        return self.__class__(x for x in self if x not in other)

    @steal_docs(set)
    def __rsub__(self, other):
        return other.__class__(x for x in other if x not in self)

    __add__ = steal_docs(set)(__or__)
    __radd__ = steal_docs(set)(__ror__)


class LimitedChangeSet(SetMixin):

    """
    Set used to limit the number of times a key can be removed/added.

    specifically deleting/adding a key only once per commit,
    optionally blocking changes to certain keys.

    >>> from snakeoil.containers import LimitedChangeSet
    >>> myset = LimitedChangeSet((1, 2), unchangable_keys=(1,))
    >>> assert 1 in myset
    >>> myset.add(1)
    >>> myset.remove(1) #doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    Unchangable: key '1' is unchangable
    >>> myset.remove(2) # remove it, so we can try adding it
    >>> assert 2 not in myset
    >>> myset.add(2) #doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    Unchangable: key '2' is unchangable

    """

    _removed = 0
    _added = 1

    @staticmethod
    def _default_key_validator(val):
        return val

    def __init__(self, initial_keys, unchangable_keys=None,
                 key_validator=None):
        """
        :param initial_keys: iterable holding the initial values to set
        :param unchangable_keys: container holding keys that cannot be changed
        :type unchangeable_keys: None, or an object supporting __contains__
        :param key_validator: callback to validate whether or not a key is usable
          for this set; primarily is an implementation detail for consumers to validate
          what consumers try adding to this set
        :type key_validator: callback taking a single argument, and returning a boolean
        """
        if key_validator is None:
            key_validator = self._default_key_validator
        self._new = set(initial_keys)
        self._validater = key_validator
        if unchangable_keys is None:
            unchangable_keys = frozenset()
        elif isinstance(unchangable_keys, (list, tuple)):
            unchangable_keys = frozenset(unchangable_keys)
        self._blacklist = unchangable_keys
        self._changed = set()
        self._change_order = []
        self._orig = frozenset(self._new)

    @steal_docs(set)
    def add(self, key):
        key = self._validater(key)
        if key in self._changed or key in self._blacklist:
            # it's been del'd already once upon a time.
            if key in self._new:
                return
            raise Unchangable(key)

        self._new.add(key)
        self._changed.add(key)
        self._change_order.append((self._added, key))

    @steal_docs(set)
    def remove(self, key):
        key = self._validater(key)
        if key in self._changed or key in self._blacklist:
            if key not in self._new:
                raise KeyError(key)
            raise Unchangable(key)

        if key in self._new:
            self._new.remove(key)
        self._changed.add(key)
        self._change_order.append((self._removed, key))

    @steal_docs(set)
    def __contains__(self, key):
        return self._validater(key) in self._new

    def changes_count(self):
        return len(self._change_order)

    def commit(self):
        self._orig = frozenset(self._new)
        self._changed.clear()
        self._change_order = []

    def rollback(self, point=0):
        l = self.changes_count()
        if point < 0 or point > l:
            raise TypeError(
                "%s point must be >=0 and <= changes_count()" % point)
        while l > point:
            change, key = self._change_order.pop(-1)
            self._changed.remove(key)
            if change == self._removed:
                self._new.add(key)
            else:
                self._new.remove(key)
            l -= 1

    def __str__(self):
        return "LimitedChangeSet([%s])" % (str(self._new)[1:-1],)

    @steal_docs(set)
    def __iter__(self):
        return iter(self._new)

    @steal_docs(set)
    def __len__(self):
        return len(self._new)

    @steal_docs(set)
    def __eq__(self, other):
        if isinstance(other, LimitedChangeSet):
            return self._new == other._new
        elif isinstance(other, (frozenset, set)):
            return self._new == other
        return False

    @steal_docs(set)
    def __ne__(self, other):
        return not self == other


class Unchangable(Exception):

    def __init__(self, key):
        Exception.__init__(self, "key '%s' is unchangable" % (key,))
        self.key = key

def _ProtectedSet_native_contains(self, key):
    return key in self._orig or key in self._new

try:
    from ._klass import ProtectedSet_contains
except ImportError:
    ProtectedSet_contains = _ProtectedSet_native_contains


class ProtectedSet(SetMixin):

    """
    Wraps a set pushing all changes into a secondary set.

    >>> from snakeoil.containers import ProtectedSet
    >>> myset = set(range(3))
    >>> protected = ProtectedSet(myset)
    >>> protected.add(4)
    >>> assert 4 not in myset
    >>> assert 4 in protected
    >>> assert 2 in protected
    >>> myset.remove(2)
    >>> assert 2 not in protected

    """
    def __init__(self, orig_set):
        self._orig = orig_set
        self._new = set()

    __contains__ = ProtectedSet_contains

    def __iter__(self):
        return chain(iter(self._new),
                     filterfalse(self._new.__contains__, self._orig))

    def __len__(self):
        return len(self._new.union(self._orig))

    def add(self, key):
        if key not in self._orig:
            self._new.add(key)


class RefCountingSet(dict):

    """
    Set implementation that implements refcounting for add/remove, removing the key only when its refcount is 0.

    This is particularly useful for essentially summing sequences that are a stream of additions/removals

    >>> from snakeoil.containers import RefCountingSet
    >>> myset = RefCountingSet()
    >>> myset.add(1)
    >>> myset.add(1)
    >>> assert list(myset) == [1]
    >>> myset.remove(1)
    >>> assert list(myset) == [1]
    >>> myset.remove(1)
    >>> assert list(myset) == []
    """

    def __init__(self, iterable=None):
        if iterable is not None:
            self.update(iterable)

    @steal_docs(set)
    def add(self, item):
        count = self.get(item, 0)
        self[item] = count + 1

    @steal_docs(set)
    def remove(self, item):
        count = self[item]
        if count == 1:
            del self[item]
        else:
            self[item] = count - 1

    @steal_docs(set)
    def discard(self, item):
        try:
            self.remove(item)
        except KeyError:
            pass

    @steal_docs(set)
    def update(self, items):
        for item in items:
            self.add(item)
