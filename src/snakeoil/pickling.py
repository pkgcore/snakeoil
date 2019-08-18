"""
pickling convenience module
"""

__all__ = (
    "iter_stream", "dump_stream",
)

from pickle import load, dump


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
