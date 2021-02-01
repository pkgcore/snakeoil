"""
Collection of functionality to make using iterators transparently easier
"""

__all__ = ("partition", "expandable_chain", "caching_iter", "iter_sort")

from collections import deque
import itertools


def partition(iterable, predicate=bool):
    """Partition an iterable into two iterables based on a given filter.

    Taking care that the predicate is called only once for each element.

    Args:
        iterable: target iterable to split into two
        predicate: filtering function used to split the iterable
    Returns:
        A tuple of iterators, the first containing items that don't match the
        filter and the second the matched items.
    """
    a, b = itertools.tee((predicate(x), x) for x in iterable)
    return ((x for pred, x in a if not pred),
            (x for pred, x in b if pred))


class expandable_chain:
    """
    chained iterables, with the ability to add new iterables to the chain
    as long as the instance hasn't raised StopIteration already.  This is
    fairly useful for implementing queues of things that must be processed.

    >>> from snakeoil.iterables import expandable_chain
    >>> l = range(5)
    >>> i = expandable_chain(l)
    >>> print(i.next())
    0
    >>> print(i.next())
    1
    >>> i.appendleft(range(5, 7))
    >>> print(i.next())
    5
    >>> print(i.next())
    6
    >>> print(i.next())
    2
    """

    __slot__ = ("iterables", "__weakref__")

    def __init__(self, *iterables):
        """
        accepts N iterables, must have at least one specified
        """
        self.iterables = deque()
        self.extend(iterables)

    def __iter__(self):
        return self

    def __next__(self):
        if self.iterables is not None:
            while self.iterables:
                try:
                    return next(self.iterables[0])
                except StopIteration:
                    self.iterables.popleft()
            self.iterables = None
        raise StopIteration()

    def append(self, iterable):
        """append an iterable to the chain to be consumed"""
        if self.iterables is None:
            raise StopIteration()
        self.iterables.append(iter(iterable))

    def appendleft(self, iterable):
        """prepend an iterable to the chain to be consumed"""
        if self.iterables is None:
            raise StopIteration()
        self.iterables.appendleft(iter(iterable))

    def extend(self, iterables):
        """extend multiple iterables to the chain to be consumed"""
        if self.iterables is None:
            raise StopIteration()
        self.iterables.extend(iter(x) for x in iterables)

    def extendleft(self, iterables):
        """prepend multiple iterables to the chain to be consumed"""
        if self.iterables is None:
            raise StopIteration()
        self.iterables.extendleft(iter(x) for x in iterables)


class caching_iter:
    """
    On demand consumes from an iterable so as to appear like a tuple

    >>> from snakeoil.iterables import caching_iter
    >>> i = iter(range(5))
    >>> ci = caching_iter(i)
    >>> print(ci[0])
    0
    >>> print(ci[2])
    2
    >>> print(i.next())
    3

    """
    __slots__ = ("iterable", "__weakref__", "cached_list", "sorter")

    def __init__(self, iterable, sorter=None):
        self.sorter = sorter
        self.iterable = iter(iterable)
        self.cached_list = []

    def __setitem__(self, key, val):
        raise TypeError("unmodifiable")

    def __getitem__(self, index):
        existing_len = len(self.cached_list)
        if self.iterable is not None and self.sorter:
            self.cached_list.extend(self.iterable)
            self.cached_list = tuple(self.sorter(self.cached_list))
            self.iterable = self.sorter = None
            existing_len = len(self.cached_list)

        if index < 0:
            if self.iterable is not None:
                self.cached_list = tuple(self.cached_list + list(self.iterable))
                self.iterable = None
                existing_len = len(self.cached_list)

            index = existing_len + index
            if index < 0:
                raise IndexError("list index out of range")

        elif index >= existing_len - 1:
            if self.iterable is not None:
                i = itertools.islice(self.iterable, 0, index - (existing_len - 1))
                self.cached_list.extend(i)
                if len(self.cached_list) -1 != index:
                    # consumed, baby.
                    self.iterable = None
                    self.cached_list = tuple(self.cached_list)
                    raise IndexError("list index out of range")

        return self.cached_list[index]

    def _flatten(self):
        if self.iterable is not None:
            if self.sorter:
                self.cached_list.extend(self.iterable)
                self.cached_list = tuple(self.sorter(self.cached_list))
                self.sorter = None
            else:
                self.cached_list = tuple(self.cached_list + list(self.iterable))
            self.iterable = None

    def __lt__(self, other):
        self._flatten()
        for x, y in itertools.zip_longest(self.cached_list, other):
            if x != y:
                return x < y
        return False

    def __gt__(self, other):
        self._flatten()
        for x, y in itertools.zip_longest(self.cached_list, other):
            if x != y:
                return x > y
        return False

    def __le__(self, other):
        return self.__lt__(other) or self.__eq__(other)

    def __ge__(self, other):
        return not self.__lt__(other)

    def __eq__(self, other):
        self._flatten()
        return self.cached_list == other

    def __ne__(self, other):
        return not self.__eq__(other)

    def __bool__(self):
        if self.cached_list:
            return True

        if self.iterable:
            for x in self.iterable:
                self.cached_list.append(x)
                return True
            # if we've made it here... then nothing more in the iterable.
            self.iterable = self.sorter = None
            self.cached_list = ()
        return False

    def __len__(self):
        if self.iterable is not None:
            self.cached_list.extend(self.iterable)
            if self.sorter:
                self.cached_list = tuple(self.sorter(self.cached_list))
                self.sorter = None
            else:
                self.cached_list = tuple(self.cached_list)
            self.iterable = None
        return len(self.cached_list)

    def __iter__(self):
        if (self.sorter is not None and
                self.iterable is not None):
            if self.cached_list:
                self.cached_list.extend(self.iterable)
                self.cached_list = tuple(self.sorter(self.cached_list))
            else:
                self.cached_list = tuple(self.sorter(self.iterable))
            self.iterable = self.sorter = None

        for x in self.cached_list:
            yield x
        if self.iterable is not None:
            for x in self.iterable:
                self.cached_list.append(x)
                yield x
        else:
            return
        self.iterable = None
        self.cached_list = tuple(self.cached_list)

    def __hash__(self):
        if self.iterable is not None:
            self.cached_list.extend(self.iterable)
            self.cached_list = tuple(self.cached_list)
            self.iterable = None
        return hash(self.cached_list)

    def __str__(self):
        return "iterable(%s), cached: %s" % (
            self.iterable, str(self.cached_list))


def iter_sort(sorter, *iterables):
    """Merge a number of sorted iterables into a single sorted iterable.

    :type sorter: callable.
    :param sorter: function, passed a list of [element, iterable].
    :param iterables: iterables to consume from.  It's **required**
       that each iterable to consume from is presorted already within
       that specific iterable.
    :return: yields items one by one in combined sorted order

    For example:

    >>> from snakeoil.iterables import iter_sort
    >>> iter1 = range(0, 5, 2)
    >>> iter2 = range(1, 6, 2)
    >>> # note that these lists will be consumed as they go,
    >>> # sorted is just being used to compare the individual items
    >>> sorted_iter = iter_sort(sorted, iter1, iter2)
    >>> print(list(sorted_iter))
    [0, 1, 2, 3, 4, 5]
    """
    l = []
    for x in iterables:
        try:
            x = iter(x)
            l.append([next(x), x])
        except StopIteration:
            pass
    if len(l) == 1:
        yield l[0][0]
        for x in l[0][1]:
            yield x
        return
    l = sorter(l)
    while l:
        yield l[0][0]
        for y in l[0][1]:
            l[0][0] = y
            break
        else:
            del l[0]
            if len(l) == 1:
                yield l[0][0]
                for x in l[0][1]:
                    yield x
                break
            continue
        l = sorter(l)
