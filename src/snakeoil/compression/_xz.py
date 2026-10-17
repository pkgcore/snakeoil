"""
xz decompression/compression

Where possible, this module defers to cpython's lzma module - if it's not available,
it defers to executing xz with tempfile arguments to do decompression
and compression.

Use this module unless it's absolutely critical that lzma module be used.
"""

__all__ = ("compress_data", "decompress_data")

import multiprocessing
import shutil

from .. import process
from ..compression import _util


def _binary():
    """Path of xz, looked up when it's needed so PATH changes are seen."""
    if (path := shutil.which("xz")) is None:
        raise process.CommandNotFound("xz")
    return path


def __getattr__(name):
    if name == "parallelizable":
        return shutil.which("xz") is not None
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


xz_compress_args = xz_decompress_args = (f"-T{multiprocessing.cpu_count()}",)

try:
    from lzma import LZMAFile
    from lzma import compress as _compress_data
    from lzma import decompress as _decompress_data

    native = True
except ImportError:
    # We need this because if we are not native then TarFile.open will fail
    # (and some code needs to be able to check that).
    native = False

    def _compress_data(data, **kwargs):
        return _util.compress_data(_binary(), data, **kwargs)

    def _decompress_data(data, **kwargs):
        return _util.decompress_data(_binary(), data, **kwargs)


def _compress_handle(handle, **kwargs):
    return _util.compress_handle(_binary(), handle, **kwargs)


def _decompress_handle(handle, **kwargs):
    return _util.decompress_handle(_binary(), handle, **kwargs)


def compress_data(data, level=9, parallelize=False):
    if parallelize and (xz := shutil.which("xz")):
        return _util.compress_data(
            xz, data, compresslevel=level, extra_args=xz_compress_args
        )
    if native:
        return _compress_data(data, preset=level)
    return _compress_data(data, compresslevel=level)


def decompress_data(data, parallelize=False):
    if parallelize and (xz := shutil.which("xz")):
        return _util.decompress_data(xz, data, extra_args=xz_decompress_args)
    return _decompress_data(data)


def compress_handle(handle, level=9, parallelize=False):
    if parallelize and (xz := shutil.which("xz")):
        return _util.compress_handle(
            xz, handle, compresslevel=level, extra_args=xz_compress_args
        )
    elif native and isinstance(handle, str):
        return LZMAFile(handle, mode="w", preset=level)
    return _compress_handle(handle, compresslevel=level)


def decompress_handle(handle, parallelize=False):
    if parallelize and (xz := shutil.which("xz")):
        return _util.decompress_handle(xz, handle, extra_args=xz_decompress_args)
    elif native and isinstance(handle, str):
        return LZMAFile(handle, mode="r")
    return _decompress_handle(handle)
