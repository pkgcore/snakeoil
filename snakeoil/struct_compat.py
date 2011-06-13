# Copyright: 2009-2010 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD

"""
Minor struct enhancements, and python version compatibility implementations

In usage, instead of importing struct you should just import this module instead.
It's designed to be a drop in replacement.
"""

__all__ = ("Struct", "error", "pack", "pack", "calcsize")

# since we're trying to be usable in struct's place, we do a start import;
# sucks, but is what it is.
from struct import *

class fake_struct(object):

    """
    Struct class implementation matching python2.5 behaviour

    This is only used if we're running python2.4
    """

    __slots__ = ("format", "size", "weakref")

    def __init__(self, format):
        """
        :param format: struct format for parsing/writing
        """
        self.format = format
        self.size = calcsize(self.format)

    def unpack(self, string):
        """
        Unpack the string containing packed C structure data, according to fmt.
        Requires len(string) == calcsize(fmt).
        """
        return unpack(self.format, string)

    def pack(self, *args):
        """Return string containing values v1, v2, ... packed according to fmt."""
        return pack(self.format, *args)


# note the struct import above; this just swaps our fake_struct in if
# we're running <python2.5
base_struct = locals().get('Struct', fake_struct)


class Struct(base_struct):

    """
    Struct extension class adding `read` and `write` methods for handling files
    """

    __slots__ = ()

    def read(self, fd):
        """given file like object `fd`, unpack a record from it"""
        return self.unpack(fd.read(self.size))

    def write(self, fd, *args):
        """given file like object `fd`, write a record from it

        args must match the number of required values for this instances
        format; see :py:func:`pack` for details.
        """
        return fd.write(self.pack(*args))
