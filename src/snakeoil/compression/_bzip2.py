"""
bzip2 decompression/compression

where possible, this module defers to cpython bz2 module- if it's not available,
it results to executing bzip2 with tempfile arguments to do decompression
and compression.

Should use this module unless its absolutely critical that bz2 module be used
"""

__all__ = ("compress_data", "decompress_data")

from functools import partial
import multiprocessing

from .. import process
from ..compression import _util

# Unused import
# pylint: disable=W0611

# if Bzip2 can't be found, throw an error.
bz2_path = process.find_binary("bzip2")


try:
    from bz2 import (compress as _compress_data,
                     decompress as _decompress_data,
                     BZ2File)
    native = True
except ImportError:

    # We need this because if we are not native then TarFile.bz2open will fail
    # (and some code needs to be able to check that).
    native = False

    _compress_data = partial(_util.compress_data, bz2_path)
    _decompress_data = partial(_util.decompress_data, bz2_path)

_compress_handle = partial(_util.compress_handle, bz2_path)
_decompress_handle = partial(_util.decompress_handle, bz2_path)

lbzip2_path = None
parallelizable = False
lbzip2_compress_args = lbzip2_decompress_args = ()
try:
    lbzip2_path = process.find_binary("lbzip2")
    lbzip2_compress_args = ('-n%i' % multiprocessing.cpu_count(),)
    lbzip2_decompress_args = lbzip2_compress_args
    parallelizable = True
except process.CommandNotFound:
    pass


def compress_data(data, level=9, parallelize=False):
    if parallelize and parallelizable:
        return _util.compress_data(lbzip2_path, data, compresslevel=level,
                                   extra_args=lbzip2_compress_args)
    return _compress_data(data, compresslevel=level)

def decompress_data(data, parallelize=False):
    if parallelize and parallelizable:
        return _util.decompress_data(lbzip2_path, data,
                                     extra_args=lbzip2_decompress_args)
    return _decompress_data(data)

def compress_handle(handle, level=9, parallelize=False):
    if parallelize and parallelizable:
        return _util.compress_handle(lbzip2_path, handle, compresslevel=level,
                                     extra_args=lbzip2_compress_args)
    elif native and isinstance(handle, str):
        return BZ2File(handle, mode='w', compresslevel=level)
    return _compress_handle(handle, compresslevel=level)

def decompress_handle(handle, parallelize=False):
    if parallelize and parallelizable:
        return _util.decompress_handle(lbzip2_path, handle,
                                       extra_args=lbzip2_decompress_args)
    elif (native and isinstance(handle, str)):
        return BZ2File(handle, mode='r')
    return _decompress_handle(handle)
