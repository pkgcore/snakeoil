# Copyright: 2006 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD

"""
bzip2 decompression/compression

where possible, this module defers to cpython bz2 module- if it's not available,
it results to executing bzip2 with tempfile arguments to do decompression
and compression.

Should use this module unless its absolutely critical that bz2 module be used
"""

__all__ = ("compress_data", "decompress_data")

from snakeoil import process, currying
from snakeoil.compression import _util

# Unused import
# pylint: disable-msg=W0611

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

    _compress_data = currying.partial(_util.compress_data, bz2_path)
    _decompress_data = currying.partial(_util.decompress_data, bz2_path)

_compress_handle = currying.partial(_util.compress_handle, bz2_path)
_decompress_handle = currying.partial(_util.decompress_handle, bz2_path)

pbzip2_path = None
parallelizable = False
try:
    pbzip2_path = process.find_binary("pbzip2")
    parallelizable = True
except process.CommandNotFound:
    pass

def compress_data(data, level=9, parallelize=False):
    if parallelize and parallelizable:
        return _util.compress_data(pbzip2_path, data, level=level)
    return _compress_data(data, compresslevel=level)

def decompress_data(data, parallelize=False):
    if parallelize and parallelizable:
        return _util.decompress_data(pbzip2_path, data)
    return _decompress_data(data)

def compress_handle(handle, level=9, parallelize=False):
    if parallelize and parallelizable:
        return _util.compress_handle(pbzip2_path, handle, level=level)
    elif native and isinstance(handle, basestring):
        return BZ2File(handle, mode='w', compresslevel=level)
    return _compress_handle(handle, level=level)

def decompress_handle(handle, parallelize=False):
    if parallelize and parallelizable:
        return _util.decompress_handle(pbzip2_path, handle)
    elif native and isinstance(handle, basestring):
        return BZ2File(handle, mode='r')
    return _decompress_handle(handle)
