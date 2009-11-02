# Copyright: 2006 Brian Harring <ferringb@gmail.com>
# License: GPL2

"""
Compatibility module providing native reimplementations of python2.5 functionality.

Uses the native implementation from C{__builtins__} if available.
"""

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

try:
    from __builtin__ import any, all
except ImportError:
    try:
        from snakeoil._compatibility import any, all
    except ImportError:
        any, all = native_any, native_all

if int(sys.version[0]) >= 3:
    import io
    file_cls = io.TextIOWrapper

    # yes this is heinous.  this is whay they recommended in the python
    # docs for porting however...
    def cmp(a, b):
        return (a < b) - (a > b)
else:
    file_cls = file
    # note that 2to3 screws this up... non issue however, since
    # this codepath won't be executed.
    from __builtin__ import cmp
