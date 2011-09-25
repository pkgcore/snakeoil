# Copyright: 2005-2011 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""
file related operations, mainly reading

Note that this originally held bash parsing functiona- for compatibility
till 0.5 of snakeoil, compatibility imports from :py:mod:`snakeoil.bash` will
be left in place here.
"""

__all__ = ("AtomicWriteFile", "read_dict", "ParseError", 'write_file',)

import os
import errno
import itertools
from snakeoil import compatibility
from snakeoil.weakrefs import WeakRefFinalizer
# kept purely for compatibility with pcheck.
from snakeoil.bash import iter_read_bash, read_bash_dict
from snakeoil import klass, compatibility
from snakeoil.currying import partial, pretty_docs
from snakeoil.demandload import demandload
demandload(globals(),
    'codecs',
    'mmap',
    'snakeoil:data_source',
    'snakeoil:_osutils_compat',
)


def write_file(path, mode, stream, encoding=None):
    f = None
    try:
        if compatibility.is_py3k:
            f = open(path, mode, encoding=encoding)
        elif encoding is not None:
            f = codecs.open(path, mode, encoding=encoding)
        else:
            f = open(path, mode)

        if compatibility.is_py3k:
            if isinstance(stream, (str, bytes)):
                stream = [stream]
        elif isinstance(stream, basestring):
            stream = [stream]

        for data in stream:
            f.write(data)
    finally:
        if f is not None:
            f.close()

def mmap_or_open_for_read(path):
    size = os.stat(path).st_size
    if size == 0:
        return (None, data_source.bytes_ro_StringIO(
            compatibiltiy.force_bytes('')))
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY)
        return (_osutils_compat.mmap_and_close(fd, size,
            mmap.MAP_SHARED, mmap.PROT_READ), None)
    except compatibility.IGNORED_EXCEPTIONS:
        raise
    except:
        try:
            os.close(fd)
        except EnvironmentError:
            pass
        raise


class AtomicWriteFile_mixin(object):

    """File class that stores the changes in a tempfile.

    Upon invocation of the close method, this class will use
    :py:func:`os.rename` to atomically replace the destination.

    Similar to file protocol behaviour, except that close *must*
    be called for the changes to be made live,

    If along the way it's decided that these changes should be discarded,
    invoke :py:func:`AtomicWriteFile.discard`; this will close the file
    without updating the target.

    If this object falls out of memory without ever being discarded nor
    closed, the contents are discarded and a warning is issued.
    """

    __metaclass__ = WeakRefFinalizer

    def __init__(self, fp, binary=False, perms=None, uid=-1, gid=-1):
        """
        :param fp: filepath to write to upon close
        :param binary: should we open the file in binary mode?
        :param perms: if specified, permissions we should force for the file.
        :param uid: if specified, the uid to force for the file.
        :param gid: if specified, the uid to force for the file.
        """
        self._is_finalized = True
        if binary:
           file_mode = "wb"
        else:
            file_mode = "w"
        self._computed_mode = file_mode
        fp = os.path.realpath(fp)
        self._original_fp = fp
        self._temp_fp = os.path.join(
            os.path.dirname(fp), ".update.%s" % os.path.basename(fp))
        old_umask = None
        if perms:
            # give it just write perms
            old_umask = os.umask(0200)
        try:
            self._actual_init()
        finally:
            if old_umask is not None:
                os.umask(old_umask)
        self._is_finalized = False
        if perms:
            os.chmod(self._temp_fp, perms)
        if (gid, uid) != (-1, -1):
            os.chown(self._temp_fp, uid, gid)

    def discard(self):
        """If we've not already flushed our changes to the target, discard them
        and close this file handle."""
        if not self._is_finalized:
            self._real_close()
            os.unlink(self._temp_fp)
            self._is_finalized = True

    def close(self):
        """Close this file handle, atomically updating the target in the process.

        Note that if we're already closed, this method does nothing
        """
        if not self._is_finalized:
            self._real_close()
            os.rename(self._temp_fp, self._original_fp)
            self._is_finalized = True

    def __del__(self):
        self.discard()


if not compatibility.is_py3k:

    class AtomicWriteFile(AtomicWriteFile_mixin, file):

        __doc__ = AtomicWriteFile_mixin.__doc__

        def _actual_init(self):
            file.__init__(self, self._temp_fp,
                mode=self._computed_mode)

        _real_close = file.close

else:
    import io
    class AtomicWriteFile(AtomicWriteFile_mixin):

        __doc__ = AtomicWriteFile_mixin.__doc__

        def _actual_init(self):
            self.raw = io.open(self._temp_fp, mode=self._computed_mode)

        def _real_close(self):
            try:
                raw = self.raw
            except AttributeError:
                # ignore it.  means that initialization flat out failed.
                return None
            return self.raw.close()

        __getattr__ = klass.GetAttrProxy("raw")


def read_dict(bash_source, splitter="=", source_isiter=False,
    allow_inline_comments=True):
    """
    read key value pairs from a file, ignoring bash-style comments.

    :param splitter: the string to split on.  Can be None to
        default to str.split's default
    :param bash_source: either a file to read from,
        or a string holding the filename to open.
    :param allow_inline_comments: whether or not to prune characters
        after a # that isn't at the start of a line.
    :raise: :py:class:`ParseError` if there are parse errors found.
    """
    d = {}
    if not source_isiter:
        filename = bash_source
        i = iter_read_bash(bash_source,
            allow_inline_comments=allow_inline_comments)
    else:
        # XXX what to do?
        filename = '<unknown>'
        i = bash_source
    line_count = 1
    try:
        for k in i:
            line_count += 1
            try:
                k, v = k.split(splitter, 1)
            except ValueError:
                if filename == "<unknown>":
                    filename = getattr(bash_source, 'name', bash_source)
                compatibility.raise_from(ParseError(filename, line_count))
            if len(v) > 2 and v[0] == v[-1] and v[0] in ("'", '"'):
                v = v[1:-1]
            d[k] = v
    finally:
        del i
    return d


class ParseError(Exception):

    """
    Exception thrown if there is a parsing error in reading a key/value dict file
    """

    def __init__(self, filename, line, errmsg=None):
        if errmsg is not None:
            Exception.__init__(self,
                               "error parsing '%s' on or before line %i: err %s" %
                               (filename, line, errmsg))
        else:
            Exception.__init__(self,
                               "error parsing '%s' on or before line %i" %
                               (filename, line))
        self.file, self.line, self.errmsg = filename, line, errmsg


def _internal_native_readfile(mode, mypath, none_on_missing=False, encoding=None,
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
        except IOError, oe:
            if none_on_missing and oe.errno == errno.ENOENT:
                return None
            raise
    finally:
        if f is not None:
            f.close()

def _mk_pretty_derived_func(func, name_base, name, *args, **kwds):
    if name:
        name = '_' + name
    return pretty_docs(partial(func, *args, **kwds),
        name='%s%s' % (name_base, name))

_mk_readfile = partial(_mk_pretty_derived_func, _internal_native_readfile,
    'readfile')

native_readfile_ascii = _mk_readfile('ascii', 'rt')
native_readfile = native_readfile_ascii
native_readfile_ascii_strict = _mk_readfile('ascii_strict', 'r',
    encoding='ascii', strict=True)
native_readfile_bytes = _mk_readfile('bytes', 'rb')
native_readfile_utf8 = _mk_readfile('utf8', 'r',
    encoding='utf8', strict=False)
native_readfile_utf8_strict = _mk_readfile('utf8_strict', 'r',
    encoding='utf8', strict=True)

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
            # have to yield /something/, else py2.4 pukes on the syntax
            yield None
        self.source.close()
        raise StopIteration()

    def close(self):
        if hasattr(self.source, 'close'):
            self.source.close()

    def __iter__(self):
        return self.iterable

def _py2k_ascii_strict_filter(source):
    any = compatibility.any
    for line in source:
        if any((0x80 & ord(char)) for char in line):
            raise ValueError("character ordinal over 127");
        yield line


def _strip_whitespace_filter(iterable):
    for line in iterable:
        yield line.strip()

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
    except IOError, ie:
        if ie.errno != errno.ENOENT or not swallow_missing:
            raise
        if none_on_missing:
            return None
        return readlines_iter(iter([]), None, close=False)

    mtime = os.fstat(handle.fileno()).st_mtime
    if not iterable:
        iterable = iter(handle)
    if not strip_whitespace:
        return readlines_iter(iterable, mtime)
    return readlines_iter(_strip_whitespace_filter(iterable), mtime,
        source=handle)


_mk_readlines = partial(_mk_pretty_derived_func, native_readlines,
    'readlines')

try:
    from snakeoil.osutils._posix import readfile, readlines
    readfile_ascii = readfile
    readlines_ascii = readlines
except ImportError:
    readfile_ascii = native_readfile_ascii
    readfile = native_readfile
    readlines_ascii = _mk_readlines('ascii', 'r',
        encoding='ascii')
    readlines = readlines_ascii

readlines_bytes = _mk_readlines('bytes', 'rb')
readlines_ascii_strict = _mk_readlines('ascii_strict', 'r',
    encoding='ascii', strict=True)
readlines_utf8 = _mk_readlines('utf8', 'r', encoding='utf8')
readlines_utf8_strict = _mk_readlines('utf8_strict', 'r',
    encoding='utf8', strict=True)

readfile_ascii_strict = native_readfile_ascii_strict
readfile_bytes = native_readfile_bytes
readfile_utf8 = native_readfile_utf8
readfile_utf8_strict = native_readfile_utf8_strict

