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

from snakeoil.demandload import demandload
demandload(globals(),
    'snakeoil.process:find_binary',
    'snakeoil.compression:_util',
    'snakeoil.currying:partial',
)

# Unused import
# pylint: disable-msg=W0611

try:
    from bz2 import compress as compress_data, decompress as decompress_data
    native = True
except ImportError:

    # We need this because if we are not native then TarFile.bz2open will fail
    # (and some code needs to be able to check that).
    native = False

    # if Bzip2 can't be found, throw an error.
    bz2_path = find_binary("bzip2")

    compress_data = partial(_util.compress_data, bz2_path)
    decompress_data = partial(_util.decompress_data, bz2_path)

