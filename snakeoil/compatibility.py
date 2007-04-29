# Copyright: 2006 Brian Harring <ferringb@gmail.com>
# License: GPL2

"""
Compatibility module providing native reimplementations of python2.5 functionality.

Uses the native implementation from C{__builtins__} if available.
"""

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

if "any" in __builtins__:
    any = any
    all = all
else:
    try:
        from snakeoil._compatibility import any, all
    except ImportError:
        any, all = native_any, native_all
