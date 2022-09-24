"""
xz decompression/compression

Where possible, this module defers to cpython's lzma module - if it's not available,
it defers to executing xz with tempfile arguments to do decompression
and compression.

Use this module unless it's absolutely critical that lzma module be used.
"""

__all__ = ("compress_data", "decompress_data")

import multiprocessing
from functools import partial

from .. import process
from ..compression import _util

# Unused import
# pylint: disable=W0611

# if xz can't be found, throw an error.
xz_path = process.find_binary("xz")
xz_compress_args = (f'-T{multiprocessing.cpu_count()}',)
xz_decompress_args = xz_compress_args
parallelizable = True

try:
    from lzma import LZMAFile
    from lzma import compress as _compress_data
    from lzma import decompress as _decompress_data
    native = True
except ImportError:

    # We need this because if we are not native then TarFile.open will fail
    # (and some code needs to be able to check that).
    native = False

    _compress_data = partial(_util.compress_data, xz_path)
    _decompress_data = partial(_util.decompress_data, xz_path)

_compress_handle = partial(_util.compress_handle, xz_path)
_decompress_handle = partial(_util.decompress_handle, xz_path)


def compress_data(data, level=9, parallelize=False):
    if parallelize and parallelizable:
        return _util.compress_data(xz_path, data, compresslevel=level,
                                   extra_args=xz_compress_args)
    if native:
        return _compress_data(data, preset=level)
    return _compress_data(data, compresslevel=level)

def decompress_data(data, parallelize=False):
    if parallelize and parallelizable:
        return _util.decompress_data(xz_path, data,
                                     extra_args=xz_decompress_args)
    return _decompress_data(data)

def compress_handle(handle, level=9, parallelize=False):
    if parallelize and parallelizable:
        return _util.compress_handle(xz_path, handle, compresslevel=level,
                                     extra_args=xz_compress_args)
    elif native and isinstance(handle, str):
        return LZMAFile(handle, mode='w', preset=level)
    return _compress_handle(handle, compresslevel=level)

def decompress_handle(handle, parallelize=False):
    if parallelize and parallelizable:
        return _util.decompress_handle(xz_path, handle,
                                       extra_args=xz_decompress_args)
    elif (native and isinstance(handle, str)):
        return LZMAFile(handle, mode='r')
    return _decompress_handle(handle)
