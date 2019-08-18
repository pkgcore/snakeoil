"""
fixed up Tarfile implementation

Specifically this grabs a copy of :py:mod:`tarfile` and applies a set of
modifications- roughly a 33% memory reduction in usage

Note that this modules initial setup semantics are technically racy- if the
python implementation allows for the GIL to be swapped to a different thread
during tarfile import (at literally the exact right moment) this version
can bleed through.  Extremely unlikely chance (haven't managed to even trigger
it once yet), but the potential seems to be there.

In usage, instead of importing tarfile you should just import this module
instead.  It's intended to be a drop in replacement.
"""

import sys
t = sys.modules.pop("tarfile", None)
tarfile = __import__("tarfile")
if t is not None:
    sys.modules["tarfile"] = t
else:
    del sys.modules["tarfile"]
del t
# ok, we now have our own local copy to monkey patch


class TarInfo(tarfile.TarInfo):

    """
    Customized TarInfo implementation.

    Note that this implementation has a locked down set of __slots__.  The slotting
    doesn't remove the underlying Dict being created (which we still pay memory for),
    but via using __slots__ we no longer pay the overallocation cost of dicts per
    TarInfo instance.

    :ivar buf: deletion and setting are disallowed in this implementation.
        This is done primarily to avoid having to have >512 bytes per TarInfo
        object.
    :ivar gname: same as TarInfo.gname, just interned via a property.
    :ivar uname: same as TarInfo.uname, just interned via a property.
    """

    if not hasattr(tarfile.TarInfo, '__slots__'):
        __slots__ = (
            "name", "mode", "uid", "gid", "size", "mtime", "chksum", "type",
            "linkname", "_uname", "_gname", "devmajor", "devminor", "prefix",
            "offset", "offset_data", "_buf", "sparse", "_link_target")
    else:
        __slots__ = ('_buf', '_uname', '_gname')

    def get_buf(self):
        return self.tobuf()

    def set_buf(self, val):
        """
        the ability to set the buffer is disabled in this
        patched version
        """

    def del_buf(self):
        """
        the ability to delete the buffer is disabled in this
        patched version
        """

    buf = property(get_buf, set_buf, del_buf)

    def get_gname(self):
        return self._gname

    def set_gname(self, val):
        self._gname = sys.intern(val)

    def del_gname(self):
        del self._gname

    gname = property(get_gname, set_gname)

    def get_uname(self):
        return self._uname

    def set_uname(self, val):
        self._uname = sys.intern(val)

    def del_uname(self):
        del self._uname

    uname = property(get_uname, set_uname)


# add in a tweaked ExFileObject that is usable by snakeoil.data_source
class ExFileObject(tarfile.ExFileObject):

    exceptions = (EnvironmentError,)


tarfile.fileobject = ExFileObject


tarfile.TarInfo = TarInfo
# finished monkey patching. now to lift things out of our tarfile
# module into this scope so from/import behaves properly.

for x in tarfile.__all__:
    locals()[x] = getattr(tarfile, x)
# pylint: disable=undefined-loop-variable
del x
