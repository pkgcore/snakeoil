# Copyright: 2005-2011 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""
file related operations, mainly reading
"""

__all__ = ("AtomicWriteFile", 'write_file', 'UnbufferedWriteHandle', 'touch')
types = [""] + list("_%s" % x for x in ("ascii", "ascii_strict", "utf8", "utf8_strict", "utf8_strict"))
__all__ += tuple("readfile%s" % x for x in types) + tuple("readlines%s" % x for x in types)
del types

from functools import partial
import os

from snakeoil import klass, compatibility
from snakeoil.currying import pretty_docs
from snakeoil.demandload import demandload
from snakeoil.weakrefs import WeakRefFinalizer

demandload(
    'codecs',
    'mmap',
    'snakeoil:data_source',
    'snakeoil:_fileutils',
)


def touch(fname, mode=0o644, **kwargs):
    """touch(1) equivalent

    :param fname: file path
    :type fname: str
    :param mode: file mode
    :type mode: octal

    See os.utime for other supported arguments.
    """
    flags = os.O_CREAT | os.O_APPEND
    if compatibility.is_py3k:
        dir_fd = kwargs.get('dir_fd', None)
        os_open = partial(os.open, dir_fd=dir_fd)
    else:
        os_open = os.open

    with os.fdopen(os_open(fname, flags, mode)) as f:
        if compatibility.is_py3k:
            os.utime(
                f.fileno() if os.utime in os.supports_fd else fname,
                dir_fd=None if os.supports_fd else dir_fd, **kwargs)
        else:
            os.utime(fname, kwargs.get('times', None))


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
        return (None, data_source.bytes_ro_StringIO(b''))
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY)
        return (_fileutils.mmap_and_close(
            fd, size, mmap.MAP_SHARED, mmap.PROT_READ), None)
    except compatibility.IGNORED_EXCEPTIONS:
        raise
    except:
        try:
            os.close(fd)
        except EnvironmentError:
            pass
        raise


class UnbufferedWriteHandle(object):
    """Class designed to work around py3k buffering issues

    see http://stackoverflow.com/questions/107705/python-output-buffering
    for background"""

    def __init__(self, stream):
        self.stream = stream

    def write(self, data):
        self.stream.write(data)
        self.stream.flush()

    #__getattr__ = klass.GetAttrProxy("stream")
    def __getattr__(self, attr):
        return getattr(self.stream, attr)


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


if not compatibility.is_py3k:

    class AtomicWriteFile(AtomicWriteFile_mixin, file):

        __doc__ = AtomicWriteFile_mixin.__doc__

        def _actual_init(self):
            file.__init__(self, self._temp_fp, mode=self._computed_mode)

        _real_close = file.close

else:
    import io
    class AtomicWriteFile(AtomicWriteFile_mixin):

        __doc__ = AtomicWriteFile_mixin.__doc__

        def _actual_init(self):
            self.raw = io.open(self._temp_fp, mode=self._computed_mode)

        def _real_close(self):
            if hasattr(self, 'raw'):
                return self.raw.close()
            return None

        __getattr__ = klass.GetAttrProxy("raw")


def _mk_pretty_derived_func(func, name_base, name, *args, **kwds):
    if name:
        name = '_' + name
    return pretty_docs(partial(func, *args, **kwds),
                       name='%s%s' % (name_base, name))

_mk_readfile = partial(_mk_pretty_derived_func, _fileutils.native_readfile,
                       'readfile')

native_readfile_ascii = _mk_readfile('ascii', 'rt')
native_readfile = native_readfile_ascii
native_readfile_ascii_strict = _mk_readfile(
    'ascii_strict', 'r', encoding='ascii', strict=True)
native_readfile_bytes = _mk_readfile('bytes', 'rb')
native_readfile_utf8 = _mk_readfile(
    'utf8', 'r', encoding='utf8', strict=False)
native_readfile_utf8_strict = _mk_readfile(
    'utf8_strict', 'r', encoding='utf8', strict=True)


_mk_readlines = partial(_mk_pretty_derived_func, _fileutils.native_readlines,
                        'readlines')

try:
    from snakeoil._posix import readfile, readlines
    readfile_ascii = readfile
    readlines_ascii = readlines
except ImportError:
    readfile_ascii = native_readfile_ascii
    readfile = native_readfile
    readlines_ascii = _mk_readlines('ascii', 'r', encoding='ascii')
    readlines = readlines_ascii

readlines_bytes = _mk_readlines('bytes', 'rb')
readlines_ascii_strict = _mk_readlines(
    'ascii_strict', 'r', encoding='ascii', strict=True)
readlines_utf8 = _mk_readlines('utf8', 'r', encoding='utf8')
readlines_utf8_strict = _mk_readlines(
    'utf8_strict', 'r', encoding='utf8', strict=True)

readfile_ascii_strict = native_readfile_ascii_strict
readfile_bytes = native_readfile_bytes
readfile_utf8 = native_readfile_utf8
readfile_utf8_strict = native_readfile_utf8_strict
