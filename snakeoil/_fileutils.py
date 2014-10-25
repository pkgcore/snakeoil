# Copyright: 2011 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD 3 clause

"""
compatibility module to break an import cycle, do not directly use this

Access this functionality from :py:module:`snakeoil.osutils` instead
"""

__all__ = ("mmap_and_close", "readlines_iter", "native_readlines",
    "native_readfile")

import errno
import itertools
import mmap
import os

from snakeoil import compatibility, demandload
demandload.demandload(globals(),
    'codecs',
)

def mmap_and_close(fd, *args, **kwargs):
    """
    see :py:obj:`mmap.mmap`; basically this maps, then closes, to ensure the
    fd doesn't bleed out.
    """
    try:
        return mmap.mmap(fd, *args, **kwargs)
    finally:
        try:
            os.close(fd)
        except EnvironmentError:
            pass


class readlines_iter(object):
    __slots__ = ("iterable", "mtime", "source")
    def __init__(self, iterable, mtime, close=True, source=None):
        if source is None:
            source = iterable
        self.source = source
        if close:
            iterable = itertools.chain(iterable, self._close_on_stop())
        self.iterable = iterable
        self.mtime = mtime

    def _close_on_stop(self):
        # we explicitly write this to force this method to be
        # a generator; we intend to return nothing, but close
        # the file on the way out.
        for x in ():
            yield None
        self.source.close()
        raise StopIteration()

    def close(self):
        if hasattr(self.source, 'close'):
            self.source.close()

    def __iter__(self):
        return self.iterable

def _native_readlines_shim(*args, **kwds):
    return native_readlines('r', *args, **kwds)

def native_readlines(mode, mypath, strip_whitespace=True, swallow_missing=False,
                     none_on_missing=False, encoding=None, strict=compatibility.is_py3k):
    """
    read a file, yielding each line

    :param mypath: fs path for the file to read
    :param strip_whitespace: strip any leading or trailing whitespace including newline?
    :param swallow_missing: throw an IOError if missing, or swallow it?
    :param none_on_missing: if the file is missing, return None, else
        if the file is missing return an empty iterable
    """
    handle = iterable = None
    try:
        if encoding and strict:
            # we special case this- codecs.open is about 2x slower,
            # thus if py3k, use the native one (which supports encoding directly)
            if compatibility.is_py3k:
                handle = open(mypath, mode, encoding=encoding)
            else:
                handle = codecs.open(mypath, mode, encoding=encoding)
                if encoding == 'ascii':
                    iterable = _py2k_ascii_strict_filter(handle)
        else:
            handle = open(mypath, mode)
    except IOError as ie:
        if not swallow_missing or ie.errno not in (errno.ENOTDIR, errno.ENOENT):
            raise
        if none_on_missing:
            return None
        return readlines_iter(iter([]), None, close=False)

    mtime = os.fstat(handle.fileno()).st_mtime
    if not iterable:
        iterable = iter(handle)
    if not strip_whitespace:
        return readlines_iter(iterable, mtime)
    return readlines_iter(_strip_whitespace_filter(iterable), mtime, source=handle)


def _strip_whitespace_filter(iterable):
    for line in iterable:
        yield line.strip()


def _py2k_ascii_strict_filter(source):
    for line in source:
        if any((0x80 & ord(char)) for char in line):
            raise ValueError("character ordinal over 127")
        yield line

def _native_readfile_shim(*args, **kwds):
    return native_readfile('r', *args, **kwds)

def native_readfile(mode, mypath, none_on_missing=False, encoding=None,
                    strict=compatibility.is_py3k):
    """
    read a file, returning the contents

    :param mypath: fs path for the file to read
    :param none_on_missing: whether to return None if the file is missing,
        else through the exception
    """
    f = None
    try:
        try:
            if encoding and strict:
                # we special case this- codecs.open is about 2x slower,
                # thus if py3k, use the native one (which supports encoding directly)
                if compatibility.is_py3k:
                    f = open(mypath, mode, encoding=encoding)
                else:
                    f = codecs.open(mypath, mode, encoding=encoding)
            else:
                f = open(mypath, mode)

            return f.read()
        except IOError as oe:
            if none_on_missing and oe.errno in (errno.ENOENT, errno.ENOTDIR):
                return None
            raise
    finally:
        if f is not None:
            f.close()
