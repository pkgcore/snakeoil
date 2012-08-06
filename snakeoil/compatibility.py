# Copyright: 2006-2011 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""
Compatibility functionality for python 2.5 through 3.2

For those of us still supporting older python versions, we're in a bit of a
bind- we'd *love* to use the newer python functions but cannot without
abandoning support for the versions we target.

This module exists to ease compatibility across multiple python versions
via indirection, and fallback implementationsso that a select subset of
newer python functionality is usable in older python versions.  Additionally,
functionality that has been moved in py3k and isn't translated by 2to3 is
accessible via this module.


For easing py3k compatibility:

* :py:data:`is_py3k` is a boolean you can rely on to indicate if you're running py2k
   or py3k
* :py:data:`is_py3k_like` is a boolean you can rely on to indicate if you're not running
  py3k, but will encounter py3k behaviour- primarily useful for instances where backports
  of py3k bits into py2.6 and py2.7 have broken previous stdlib behaviour.
* :py:func:`intern` is accessible from here
* :py:func:`sorted_cmp`, :py:func:`sort_cmp`, :py:func:`cmp` are available for easing
  compatibility across py2k/py3k for comparison and sorting args; these implementations by
  default defer to the builtins whenever they're available, only kicking in when needed.
* :py:func:`force_bytes` is useful for if you know you'll need a bytes string under py3k,
  but cannot force a minimal python version of 2.6 to get that syntax.  Essentially instead of
  writing b'content', you would write force_bytes("content").  Under py3k, you get a bytes object,
  under py2k you get a plain old string w/ minimal overhead.
"""

__all__ = ("all", "any", "is_py3k", "is_py3k_like", "next",
    "intern", "cmp", "sorted_cmp", "sort_cmp")

import sys


# figure out if we're jython or not...
is_jython = False
if hasattr(sys, 'getPlatform'):
    is_jython = 'java' in sys.getPlatform().lower()


# using variable before assignment
# pylint: disable-msg=E0601

is_py3k = int(sys.version[0]) == 3
is_py3k_like = is_py3k or float(sys.version[:3]) >= 2.7

# Imported for compatibility w/ old code that was using us for 2.4 compatibility.
from __builtin__ import any, all

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

    def force_bytes(string):
        return string.encode()

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

    force_bytes = str

def native_is_disjoint(src_set, sequence):
    return not src_set.intersection(sequence)

if hasattr(set(), 'isdisjoint'):
    # python2.6 and up.
    def is_disjoint(instance, *args):
        return instance.isdisjoint(*args)
else:
    is_disjoint = native_is_disjoint
import sys

if is_py3k:
    def raise_from(new_exception, exc_info=None):
        if exc_info is None:
            exc_info = sys.exc_info()
        new_exception.__context__ = new_exception.__cause__ = exc_info[1]
        new_exception.__traceback__ = exc_info[2]
        raise new_exception
else:
    def raise_from(new_exception, exc_info=None):
        if exc_info is None:
            exc_info = sys.exc_info()

        #exc_info format; class, instance, tb

        new_exception.__cause__ = exc_info[1]
        raise new_exception.__class__, new_exception, exc_info[2]

IGNORED_EXCEPTIONS = (RuntimeError, MemoryError, SystemExit, KeyboardInterrupt)
