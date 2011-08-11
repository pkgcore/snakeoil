# Copyright: 2005-2010 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""
file related operations, mainly reading

Note that this originally held bash parsing functiona- for compatibility
till 0.5 of snakeoil, compatibility imports from :py:mod:`snakeoil.bash` will
be left in place here.
"""

__all__ = ("AtomicWriteFile", "read_dict", "ParseError")

import os
from snakeoil import compatibility
from snakeoil.weakrefs import WeakRefFinalizer
from snakeoil.bash import *
from snakeoil import klass

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
                raise ParseError(filename, line_count)
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
