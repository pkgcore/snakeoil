"""
Minor struct enhancements, and python version compatibility implementations

This is deprecated.  Use :py:mod:`struct`, with ``s.unpack(fd.read(s.size))``
and ``fd.write(s.pack(...))`` in place of ``Struct.read`` and ``Struct.write``.
"""

__all__ = ("Struct", "error", "unpack", "pack")

# since we're trying to be usable in struct's place, we do a start import;
# sucks, but is what it is.
# pylint: disable=wildcard-import,unused-wildcard-import

from struct import Struct as base_struct
from struct import error, pack, unpack

from ._internals import deprecated

deprecated.module(
    "Use struct",
    qualname="snakeoil.struct_compat",
    removal_in=(0, 12, 0),
)


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
