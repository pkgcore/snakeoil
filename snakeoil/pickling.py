# Copyright: 2007 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""
convenience module using cPickle if available, else failing back to pickle
"""

try:
    from cPickle import *
except ImportError:
    from pickle import *

def iter_stream(stream):
    try:
        while True:
            yield load(stream)
    except EOFError:
        pass

def dump_stream(handle, stream):
    for item in stream:
        dump(item, handle)
