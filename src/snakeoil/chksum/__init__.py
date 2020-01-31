"""
chksum verification/generation subsystem
"""

from importlib import import_module
import os
import sys

from .. import osutils, klass
from .defaults import chksum_loop_over_file


chksum_types = {}
__inited__ = False


class MissingChksumHandler(Exception):
    """A requested checksum handler doesn't exist on the system."""


def get_handler(requested):

    """
    get a chksum handler

    :raise MissingChksumHandler: if chksum type has no registered handler
    :return: chksum handler (callable)
    """

    if not __inited__:
        init()
    if requested not in chksum_types:
        raise MissingChksumHandler("no handler for %s" % requested)
    return chksum_types[requested]


def get_handlers(requested=None):

    """
    get multiple chksum handlers

    :param requested: None (all handlers), or a sequence of the specific
        handlers desired.
    :raise MissingChksumHandler: if requested chksum type has no registered handler
    :return: dict of chksum_type:chksum handler
    """

    if requested is None:
        if not __inited__:
            init()
        return dict(chksum_types)
    d = {}
    for x in requested:
        d[x] = get_handler(x)
    return d


def init(additional_handlers=None):

    """
    init the chksum subsystem.

    Scan dirname(__file__), find what handlers are available, and load them.

    :param additional_handlers: None, or pass in a dict of type:func
    """

    global __inited__ # pylint: disable=global-statement

    if additional_handlers is not None and not isinstance(
            additional_handlers, dict):
        raise TypeError("additional handlers must be a dict!")

    chksum_types.clear()
    __inited__ = False
    loc = os.path.dirname(sys.modules[__name__].__file__)
    for f in osutils.listdir_files(loc):
        if not f.endswith(".py") or f.startswith("__init__."):
            continue
        try:
            i = f.find(".")
            if i != -1:
                f = f[:i]
            del i
            m = import_module(__name__ + "." + f)
        except ImportError:
            continue
        try:
            types = getattr(m, "chksum_types")
        except AttributeError:
            # no go.
            continue
        chksum_types.update(types)

    if additional_handlers is not None:
        chksum_types.update(additional_handlers)

    __inited__ = True


def get_chksums(location, *chksums, **kwds):
    """
    run multiple chksumers over a data_source/file path

    Note that if you need multiple chksums for a file, you should invoke this with
    all desired chksums- the implementation will do some internal efficiency tricks
    (doing the IO once for example).

    :param location: either a data_source, or a filepath to generate chksum data for
    :param chksums: variable arg, the name of the chksums desired.  These need to
        be valid chksums known in `chksum_types`
    :return: a list of chksums, matching the order of requested chksums
    """

    if not chksums:
        # dumb api invocation...
        return []

    handlers = get_handlers(chksums)
    # try to hand off to the per file handler, may be faster.
    if len(chksums) == 1:
        return [handlers[chksums[0]](location)]
    if len(chksums) == 2 and 'size' in chksums:
        parallelize = False
    else:
        parallelize = kwds.get("parallelize", True)
    can_mmap = True
    for k in chksums:
        can_mmap &= handlers[k].can_mmap
    return chksum_loop_over_file(location, [handlers[k].new() for k in chksums],
                                 parallelize=parallelize, can_mmap=can_mmap)


class LazilyHashedPath(metaclass=klass.immutable_instance):
    """Given a pathway, compute chksums on demand via attribute access."""

    def __init__(self, path, **initial_values):
        f = object.__setattr__
        f(self, 'path', path)
        for attr, val in initial_values.items():
            f(self, attr, val)

    def __getattr__(self, attr):
        if not attr.islower():
            # Disallow sHa1.
            raise AttributeError(attr)
        elif attr == 'mtime':
            val = osutils.stat_mtime_long(self.path)
        else:
            try:
                val = get_chksums(self.path, attr)[0]
            except MissingChksumHandler as e:
                raise AttributeError(attr) from e
        object.__setattr__(self, attr, val)
        return val

    def clear(self):
        for key in get_handlers():
            if hasattr(self, key):
                delattr(self, key)

    def __getstate__(self):
        return self.__dict__.copy()

    def __setstate__(self, state):
        for k, v in state.items():
            object.__setattr__(self, k, v)
