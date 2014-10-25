# Copyright: 2005-2011 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""
sequence related operations and classes
"""

from __future__ import print_function

__all__ = ("unstable_unique", "stable_unique", "iter_stable_unique",
    "iflatten_instance", "iflatten_func", "ChainedLists", "predicate_split")

from snakeoil.compatibility import is_py3k
from snakeoil.iterables import expandable_chain
from snakeoil.klass import steal_docs


def unstable_unique(sequence):
    """
    Given a sequence, return a list of the unique items without preserving ordering

    """

    try:
        n = len(sequence)
    except TypeError:
        # if it doesn't support len, assume it's an iterable
        # and fallback to the slower stable_unique
        return stable_unique(sequence)
    # assume all elements are hashable, if so, it's linear
    try:
        return list(set(sequence))
    except TypeError:
        pass

    # so much for linear.  abuse sort.
    try:
        t = sorted(sequence)
    except TypeError:
        pass
    else:
        assert n > 0
        last = t[0]
        lasti = i = 1
        while i < n:
            if t[i] != last:
                t[lasti] = last = t[i]
                lasti += 1
            i += 1
        return t[:lasti]

    # blah.  back to original portage.unique_array
    u = []
    for x in sequence:
        if x not in u:
            u.append(x)
    return u


def stable_unique(iterable):
    """
    Given a sequence, return a list of the unique items while preserving ordering

    For performance reasons, only use this if you really do need to preserve the ordering.
    """
    return list(iter_stable_unique(iterable))


def iter_stable_unique(iterable):
    """
    Given a sequence, yield unique items while preserving ordering

    For performance reasons, only use this if you really do need to preserve the ordering.
    """
    s = set()
    sadd = s.add
    sl = []
    slappend = sl.append
    iterable = iter(iterable)
    # the reason for this structuring is purely speed- entering try/except
    # repeatedly is costly, thus structure it to penalize the unhashables
    # instead of penalizing the hashables.
    while True:
        try:
            for x in iterable:
                if x not in s:
                    yield x
                    sadd(x)
        except TypeError:
            # unhashable item...
            if x not in sl:
                yield x
                slappend(x)
            continue
        break

if is_py3k:
    _str_kls = (str, bytes)
else:
    _str_kls = basestring
def native_iflatten_instance(l, skip_flattening=_str_kls):
    """
    collapse [[1],2] into [1,2]

    :param skip_flattening: list of classes to not descend through
    :return: this generator yields each item that cannot be flattened (or is
        skipped due to being a instance of ``skip_flattening``)
    """
    if isinstance(l, skip_flattening):
        yield l
        return
    iters = expandable_chain(l)
    try:
        while True:
            x = iters.next()
            if hasattr(x, '__iter__') and not (isinstance(x, skip_flattening)
                or (isinstance(x, _str_kls) and len(x) == 1)):
                iters.appendleft(x)
            else:
                yield x
    except StopIteration:
        pass


def native_iflatten_func(l, skip_func):
    """
    collapse [[1],2] into [1,2]

    :param skip_func: a callable that returns True when iflatten_func should
        descend no further
    :return: this generator yields each item that cannot be flattened (or is
        skipped due to a True result from skip_func)
    """
    if skip_func(l):
        yield l
        return
    iters = expandable_chain(l)
    try:
        while True:
            x = iters.next()
            if hasattr(x, '__iter__') and not skip_func(x):
                iters.appendleft(x)
            else:
                yield x
    except StopIteration:
        pass


try:
    # No name "readdir" in module osutils
    # pylint: disable=E0611
    from snakeoil._lists import iflatten_instance, iflatten_func
    cpy_builtin = True
except ImportError:
    cpy_builtin = False
    cpy_iflatten_instance = cpy_iflatten_func = None
    iflatten_instance = native_iflatten_instance
    iflatten_func = native_iflatten_func


class ChainedLists(object):
    """
    Given a set of sequences, this will act as a proxy to them without collapsing them
    into a single list.

    This is primarily useful when you're dealing in large sets (or custom sequence objects),
    and do not want to collapse them into one sequence- but you still want to be able to access
    them as if they were one sequence.

    Note that while you can add more lists onto this, you cannot directly change the underlying
    lists through this class.

    >>> from snakeoil.lists import ChainedLists
    >>> l1, l2 = [0, 1, 2, 3], [4,5,6]
    >>> cl = ChainedLists(l1, l2)
    >>> print(cl[3])
    3
    >>> print(cl[4])
    4
    >>> print(cl[0])
    0
    >>> assert 4 in cl
    >>> print(len(cl))
    7
    >>> cl[0] = 9
    Traceback (most recent call last):
    TypeError: not mutable
    """
    __slots__ = ("_lists", "__weakref__")

    def __init__(self, *lists):
        """
        all args must be sequences
        """
        # ensure they're iterable
        for x in lists:
            iter(x)

        if isinstance(lists, tuple):
            lists = list(lists)
        self._lists = lists

    def __len__(self):
        return sum(len(l) for l in self._lists)

    def __getitem__(self, idx):
        if idx < 0:
            idx += len(self)
            if idx < 0:
                raise IndexError
        for l in self._lists:
            l2 = len(l)
            if idx < l2:
                return l[idx]
            idx -= l2
        else:
            raise IndexError

    def __setitem__(self, idx, val):
        raise TypeError("not mutable")

    def __delitem__(self, idx):
        raise TypeError("not mutable")

    def __iter__(self):
        for l in self._lists:
            for x in l:
                yield x

    def __contains__(self, obj):
        return obj in iter(self)

    def __str__(self):
        return "[ %s ]" % ", ".join(str(l) for l in self._lists)

    @steal_docs(list)
    def append(self, item):
        self._lists.append(item)

    @steal_docs(list)
    def extend(self, items):
        self._lists.extend(items)


def predicate_split(func, stream, key=None):
    """
    Given a stream and a function, split the stream into two sequences based on
    the results of the func for that item

    :param func: function to invoke with the item; function must return True or False
    :param stream: iterable to split into two sequences
    :param key: if set, a function to use to pull the attribute to inspect.  Basically
        the same sort of trick as the key paramater for :py:func:`sorted`
    :return: two lists, the first a list of everything that was False, the second a
        list of everything that was True

    Example Usage:

    >>> from snakeoil.lists import predicate_split
    >>> odd, even = predicate_split(lambda x:x % 2 == 0, range(10))
    >>> assert odd == [1, 3, 5, 7, 9]
    >>> assert even == [0, 2, 4, 6, 8]
    """
    true_l, false_l = [], []
    tappend, fappend = true_l.append, false_l.append
    # needs to be fast... this this since a simple
    # lambda x:x # is a bit more of a killer then you would think.
    if key is not None:
        for item in stream:
            if func(key(item)):
                tappend(item)
            else:
                fappend(item)
    else:
        for item in stream:
            if func(item):
                tappend(item)
            else:
                fappend(item)
    return false_l, true_l
