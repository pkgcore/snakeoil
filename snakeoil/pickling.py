# Copyright: 2007-2010 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""
convenience module using cPickle if available, else failing back to pickle.

Instead of writing your own try/except ImportError code for trying to access
cPickle, just import this instead- it does exactly that internally
"""

__all__ = (
    "iter_stream", "dump_stream", "PickleError", "PicklingError",
    "UnpicklingError", "Pickler", "Unpickler", "dump", "dumps", "load", "loads",
)

# pylint: disable=wildcard-import,unused-wildcard-import
try:
    from cPickle import *
except ImportError:
    from pickle import *


def iter_stream(stream):
    """
    given a filehandle to consume from, yield pickled objects from it.

    This is useful in conjunction with :py:func:`dump_stream` to serialize
    items as you go, rather than in one single shot.

    :param stream: file like object to continually try consuming pickled
        data from until EOF is reached.
    """
    try:
        while True:
            yield load(stream)
    except EOFError:
        pass


def dump_stream(handle, stream):
    """
    given a filehandle to write to, write pickled objects to it.

    This is useful in conjunction with :py:func:`iter_stream` to deserialize
    the results of this function- specifically you use dump_stream to flush it
    to disk as you go, and iter_stream to load it back as you go.

    :param handle: file like object to write to
    :param stream: iterable of objects to pickle and write to handle
    """
    for item in stream:
        dump(item, handle)
