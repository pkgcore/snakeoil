# Copyright: 2005-2010 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""
file related operations, mainly reading
"""

import os
from snakeoil import compatibility
from snakeoil.weakrefs import WeakRefFinalizer
from snakeoil.bash import *

__all__ = ("AtomicWriteFile", "read_dict", "ParseError")

class AtomicWriteFile_mixin(object):

    """File class that stores the changes in a tempfile.

    Upon close call, uses rename to replace the destination.

    Similar to file protocol behaviour, except for the C{__init__}, and
    that close *must* be called for the changes to be made live,

    if C{__del__} is triggered it's assumed that an exception occured,
    thus the changes shouldn't be made live.
    """

    __metaclass__ = WeakRefFinalizer

    def __init__(self,fp, binary=False, perms=None, uid=-1, gid=-1):
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
        if not self._is_finalized:
            self._real_close()
            os.unlink(self._temp_fp)
            self._is_finalized = True

    def close(self):
        if not self._is_finalized:
            self._real_close()
            os.rename(self._temp_fp, self._original_fp)
            self._is_finalized = True

    def __del__(self):
        self.discard()

if not compatibility.is_py3k:

    class AtomicWriteFile(AtomicWriteFile_mixin, compatibility.file_cls):

        def _actual_init(self):
            compatibility.file_cls.__init__(self, self._temp_fp,
                mode=self._computed_mode)

        _real_close = compatibility.file_cls.close

else:
    import io
    class AtomicWriteFile(AtomicWriteFile_mixin):

        def _actual_init(self):
            self.raw = io.open(self._temp_fp, mode=self._computed_mode)

        def _real_close(self):
            try:
                raw = self.raw
            except AttributeError:
                # ignore it.  means that initialization flat out failed.
                return None
            return self.raw.close()

        def __getattr__(self, attr):
            # use object.__getattribute__ to ensure we don't go recursive
            # here if initialization failed during init
            return getattr(object.__getattribute__(self, 'raw'), attr)

def read_dict(bash_source, splitter="=", source_isiter=False,
    allow_inline_comments=True):
    """
    read key value pairs, ignoring bash-style comments.

    @param splitter: the string to split on.  Can be None to
        default to str.split's default
    @param bash_source: either a file to read from,
        or a string holding the filename to open.
    @param allow_inline_comments: whether or not to prune characters
        after a # that isn't at the start of a line.
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
                    if isinstance(bash_source, compatibility.file_cls):
                        raise ParseError(bash_source.name, line_count)
                    else:
                        raise ParseError(bash_source, line_count)
                else:
                    raise ParseError(filename, line_count)
            if len(v) > 2 and v[0] == v[-1] and v[0] in ("'", '"'):
                v = v[1:-1]
            d[k] = v
    finally:
        del i
    return d


class ParseError(Exception):

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
