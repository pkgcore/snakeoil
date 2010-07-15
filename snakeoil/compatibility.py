# Copyright: 2006 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""
Compatibility module providing native reimplementations of python2.5 functionality.

Uses the native implementation from C{__builtins__} if available.
"""

__all__ = ("all", "any", "is_py3k", "is_py3k_like", "next",
    "intern", "cmp", "sorted_cmp", "sort_cmp")

import sys

def native_any(iterable):
    for x in iterable:
        if x:
            return True
    return False

def native_all(iterable):
    for x in iterable:
        if not x:
            return False
    return True

# using variable before assignment
# pylint: disable-msg=E0601

is_py3k = int(sys.version[0]) == 3
is_py3k_like = is_py3k or float(sys.version[:3]) >= 2.7

try:
    from __builtin__ import any, all
except ImportError:
    try:
        from snakeoil._compatibility import any, all
    except ImportError:
        any, all = native_any, native_all

def sorted_key_from_cmp(cmp_func, key_func=None):
    class _key_proxy(object):

        __slots__ = ('_obj',)

        if key_func: # done this way for speed reasons.
            def __init__(self, obj, key_convert=key_func):
                self._obj = key_convert(obj)
        else:
            def __init__(self, obj):
                self._obj = obj

        def __lt__(self, other, _cmp_func=cmp_func):
            return _cmp_func(self._obj, other._obj) < 0

    return _key_proxy


if is_py3k:
    # yes this is heinous.  this is whay they recommended in the python
    # docs for porting however...
    def raw_cmp(a, b):
        return (a > b) - (a < b)

    def cmp(obj1, obj2, cmp=raw_cmp):
        if obj1 is None:
            if obj2 is None:
                return 0
            return -1
        elif obj2 is None:
            return 1
        return raw_cmp(obj1, obj2)

    intern = sys.intern
    from __builtin__ import next

    def sorted_cmp(sequence, func, key=None, reverse=False):
        return sorted(sequence, reverse=reverse,
            key=sorted_key_from_cmp(func, key_func=key))

    def sort_cmp(list_inst, func, key=None, reverse=False):
        list_inst.sort(reverse=reverse,
            key=sorted_key_from_cmp(func, key_func=key))

else:
    # note that 2to3 screws this up... non issue however, since
    # this codepath won't be executed.
    from __builtin__ import cmp, intern
    def next(iterable):
        try:
            obj = iterable.next
        except AttributeError:
            raise TypeError("%s is not an iterator" % (iterable,))
        return obj()

    def sorted_cmp(sequence, func, key=None, reverse=False):
        return sorted(sequence, cmp=func, key=key, reverse=reverse)

    def sort_cmp(list_inst, func, key=None, reverse=False):
        return list_inst.sort(cmp=func, key=key, reverse=reverse)
