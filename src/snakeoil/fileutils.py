"""
file related operations, mainly reading
"""

__all__ = ("AtomicWriteFile", 'write_file', 'UnbufferedWriteHandle', 'touch')
types = [""] + list("_%s" % x for x in ("ascii", "utf8"))
__all__ += tuple("readfile%s" % x for x in types) + tuple("readlines%s" % x for x in types)
del types

from functools import partial
import mmap
import os

from . import _fileutils, data_source
from .compatibility import IGNORED_EXCEPTIONS
from .currying import pretty_docs
from .klass import GetAttrProxy


def touch(fname, mode=0o644, **kwargs):
    """touch(1) equivalent

    :param fname: file path
    :type fname: str
    :param mode: file mode
    :type mode: octal

    See os.utime for other supported arguments.
    """
    flags = os.O_CREAT | os.O_APPEND
    dir_fd = kwargs.get('dir_fd', None)
    os_open = partial(os.open, dir_fd=dir_fd)

    with os.fdopen(os_open(fname, flags, mode)) as f:
        os.utime(
            f.fileno() if os.utime in os.supports_fd else fname,
            dir_fd=None if os.supports_fd else dir_fd, **kwargs)


def write_file(path, mode, stream, encoding=None):
    f = None
    try:
        f = open(path, mode, encoding=encoding)
        if isinstance(stream, (str, bytes)):
            stream = [stream]
        for data in stream:
            f.write(data)
    finally:
        if f is not None:
            f.close()

def mmap_or_open_for_read(path):
    size = os.stat(path).st_size
    if size == 0:
        return (None, data_source.bytes_ro_StringIO(b''))
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY)
        return (_fileutils.mmap_and_close(
            fd, size, mmap.MAP_SHARED, mmap.PROT_READ), None)
    except IGNORED_EXCEPTIONS:
        raise
    except:
        try:
            os.close(fd)
        except EnvironmentError:
            pass
        raise


class UnbufferedWriteHandle:
    """Class designed to work around py3k buffering issues

    see http://stackoverflow.com/questions/107705/python-output-buffering
    for background"""

    def __init__(self, stream):
        self.stream = stream

    def write(self, data):
        self.stream.write(data)
        self.stream.flush()

    __getattr__ = GetAttrProxy("stream")


class AtomicWriteFile_mixin:

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
            old_umask = os.umask(0o0200)
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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc is not None:
            self.discard()
        else:
            self.close()

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


class AtomicWriteFile(AtomicWriteFile_mixin):

    __doc__ = AtomicWriteFile_mixin.__doc__

    def _actual_init(self):
        self.raw = open(self._temp_fp, mode=self._computed_mode)

    def _real_close(self):
        if hasattr(self, 'raw'):
            return self.raw.close()
        return None

    __getattr__ = GetAttrProxy("raw")


def _mk_pretty_derived_func(func, name_base, name, *args, **kwds):
    if name:
        name = '_' + name
    return pretty_docs(partial(func, *args, **kwds),
                       name='%s%s' % (name_base, name))


_mk_readfile = partial(
    _mk_pretty_derived_func, _fileutils.native_readfile, 'readfile')

readfile_ascii = _mk_readfile('ascii', 'rt')
readfile_bytes = _mk_readfile('bytes', 'rb')
readfile_utf8 = _mk_readfile('utf8', 'r', encoding='utf8')
readfile = readfile_utf8


_mk_readlines = partial(
    _mk_pretty_derived_func, _fileutils.native_readlines, 'readlines')

readlines_ascii = _mk_readlines('ascii', 'r', encoding='ascii')
readlines_bytes = _mk_readlines('bytes', 'rb')
readlines_utf8 = _mk_readlines('utf8', 'r', encoding='utf8')
readlines = readlines_utf8
