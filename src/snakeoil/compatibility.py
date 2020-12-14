"""
Compatibility functionality stubs
"""

__all__ = ("cmp", "sorted_cmp", "sort_cmp")

import sys


def sorted_key_from_cmp(cmp_func, key_func=None):
    class _key_proxy:

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


# yes this is heinous.  this is what they recommended in the python
# docs for porting however...
def _raw_cmp(a, b):
    return (a > b) - (a < b)


def cmp(obj1, obj2, raw_cmp=_raw_cmp):
    if obj1 is None:
        if obj2 is None:
            return 0
        return -1
    elif obj2 is None:
        return 1
    return raw_cmp(obj1, obj2)


def sorted_cmp(sequence, func, key=None, reverse=False):
    return sorted(sequence, reverse=reverse,
                  key=sorted_key_from_cmp(func, key_func=key))


def sort_cmp(list_inst, func, key=None, reverse=False):
    list_inst.sort(reverse=reverse,
                   key=sorted_key_from_cmp(func, key_func=key))


IGNORED_EXCEPTIONS = (RuntimeError, MemoryError, SystemExit, KeyboardInterrupt)
