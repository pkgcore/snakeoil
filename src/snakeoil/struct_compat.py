"""
Minor struct enhancements, and python version compatibility implementations

In usage, instead of importing struct you should just import this module instead.
It's designed to be a drop in replacement.
"""

__all__ = ("Struct", "error", "pack", "pack", "calcsize")

# since we're trying to be usable in struct's place, we do a start import;
# sucks, but is what it is.
# pylint: disable=wildcard-import,unused-wildcard-import
from struct import *

base_struct = Struct


# pylint: disable=function-redefined
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
