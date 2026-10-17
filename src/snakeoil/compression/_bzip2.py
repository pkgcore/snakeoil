"""
bzip2 decompression/compression

Where possible, this module defers to cpython's bz2 module - if it's not available,
it defers to executing bzip2 with tempfile arguments to do decompression
and compression.

Use this module unless it's absolutely critical that the bz2 module is used.
"""

__all__ = ("compress_data", "decompress_data")

import multiprocessing
import shutil

from .. import process
from ..compression import _util


def _binary(name):
    """Path of *name*, looked up when it's needed so PATH changes are seen."""
    if (path := shutil.which(name)) is None:
        raise process.CommandNotFound(name)
    return path


def __getattr__(name):
    if name == "parallelizable":
        return shutil.which("lbzip2") is not None
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


try:
    from bz2 import BZ2File
    from bz2 import compress as _compress_data
    from bz2 import decompress as _decompress_data

    native = True
except ImportError:
    # We need this because if we are not native then TarFile.bz2open will fail
    # (and some code needs to be able to check that).
    native = False

    def _compress_data(data, **kwargs):
        return _util.compress_data(_binary("bzip2"), data, **kwargs)

    def _decompress_data(data, **kwargs):
        return _util.decompress_data(_binary("bzip2"), data, **kwargs)


def _compress_handle(handle, **kwargs):
    return _util.compress_handle(_binary("bzip2"), handle, **kwargs)


def _decompress_handle(handle, **kwargs):
    return _util.decompress_handle(_binary("bzip2"), handle, **kwargs)


lbzip2_compress_args = lbzip2_decompress_args = (f"-n{multiprocessing.cpu_count()}",)


def compress_data(data, level=9, parallelize=False):
    if parallelize and (lbzip2 := shutil.which("lbzip2")):
        return _util.compress_data(
            lbzip2,
            data,
            compresslevel=level,
            extra_args=lbzip2_compress_args,
        )
    return _compress_data(data, compresslevel=level)


def decompress_data(data, parallelize=False):
    if parallelize and (lbzip2 := shutil.which("lbzip2")):
        return _util.decompress_data(lbzip2, data, extra_args=lbzip2_decompress_args)
    return _decompress_data(data)


def compress_handle(handle, level=9, parallelize=False):
    if parallelize and (lbzip2 := shutil.which("lbzip2")):
        return _util.compress_handle(
            lbzip2,
            handle,
            compresslevel=level,
            extra_args=lbzip2_compress_args,
        )
    elif native and isinstance(handle, str):
        return BZ2File(handle, mode="w", compresslevel=level)
    return _compress_handle(handle, compresslevel=level)


def decompress_handle(handle, parallelize=False):
    if parallelize and (lbzip2 := shutil.which("lbzip2")):
        return _util.decompress_handle(
            lbzip2, handle, extra_args=lbzip2_decompress_args
        )
    elif native and isinstance(handle, str):
        return BZ2File(handle, mode="r")
    return _decompress_handle(handle)
