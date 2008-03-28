# Copyright: 2005-2007 Brian Harring <ferringb@gmail.com>
# License: GPL2

"""
collection of container classes
"""

from snakeoil.demandload import demandload
demandload(
    globals(),
    'itertools:chain,ifilterfalse',
)

class InvertedContains(set):

    """Set that inverts all contains lookup results.

    Mainly useful in conjuection with LimitedChangeSet for converting
    from blacklist to whitelist.

    Cannot be iterated over.
    """

    def __contains__(self, key):
        return not set.__contains__(self, key)

    def __iter__(self):
        # infinite set, non iterable.
        raise TypeError("InvertedContains cannot be iterated over")


class SetMixin(object):
    """
    A mixin providing set methods.

    Subclasses should provide __init__, __iter__ and __contains__.
    """

    def __and__(self, other, kls=None):
        # Note: for these methods we don't bother to filter dupes from this
        # list -  since the subclasses __init__ should already handle this,
        # there's no point doing it twice.
        return (kls or self.__class__)(x for x in self if x in other)

    def __rand__(self, other):
        return self.__and__(other, kls=other.__class__)

    def __or__(self, other, kls=None):
        return (kls or self.__class__)(chain(self, other))

    def __ror__(self, other):
        return self.__or__(other, kls=other.__class__)

    def __xor__(self, other, kls=None):
        return (kls or self.__class__)(chain((x for x in self if x not in other),
                         (x for x in other if x not in self)))

    def __rxor__(self, other):
        return self.__xor__(other, kls=other.__class__)

    def __sub__(self, other):
        return self.__class__(x for x in self if x not in other)

    def __rsub__(self, other):
        return other.__class__(x for x in other if x not in self)

    __add__ = __or__
    __radd__ = __ror__


class LimitedChangeSet(SetMixin):

    """Set used to limit the number of times a key can be removed/added.

    specifically deleting/adding a key only once per commit,
    optionally blocking changes to certain keys.
    """

    _removed    = 0
    _added      = 1

    def __init__(self, initial_keys, unchangable_keys=None,
        key_validator=lambda x:x):
        self._new = set(initial_keys)
        self._validater = key_validator
        if unchangable_keys is None:
            self._blacklist = []
        else:
            if isinstance(unchangable_keys, (list, tuple)):
                unchangable_keys = set(unchangable_keys)
            self._blacklist = unchangable_keys
        self._changed = set()
        self._change_order = []
        self._orig = frozenset(self._new)

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
        return str(self._new).replace("set(", "LimitedChangeSet(", 1)

    def __iter__(self):
        return iter(self._new)

    def __len__(self):
        return len(self._new)

    def __eq__(self, other):
        if isinstance(other, LimitedChangeSet):
            return self._new == other._new
        elif isinstance(other, (frozenset, set)):
            return self._new == other
        return False

    def __ne__(self, other):
        return not (self == other)


class Unchangable(Exception):

    def __init__(self, key):
        Exception.__init__(self, "key '%s' is unchangable" % (key,))
        self.key = key


class ProtectedSet(SetMixin):

    """
    Wraps a set pushing all changes into a secondary set.
    """
    def __init__(self, orig_set):
        self._orig = orig_set
        self._new = set()

    def __contains__(self, key):
        return key in self._orig or key in self._new

    def __iter__(self):
        return chain(iter(self._new),
            ifilterfalse(self._new.__contains__, self._orig))

    def __len__(self):
        return len(self._orig.union(self._new))

    def add(self, key):
        if key not in self._orig:
            self._new.add(key)


class RefCountingSet(dict):

    def __init__(self, iterable=None):
        if iterable is not None:
            dict.__init__(self, ((x, 1) for x in iterable))

    def add(self, item):
        count = self.get(item, 0)
        self[item] = count + 1

    def remove(self, item):
        count = self[item]
        if count == 1:
            del self[item]
        else:
            self[item] = count - 1
