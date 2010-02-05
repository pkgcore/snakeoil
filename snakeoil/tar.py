# Copyright: 2006-2009 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""
tar file access

monkey patching of stdlib tarfile to reduce mem usage (33% reduction).

note this is also racey; N threads trying an import, if they're after
the *original* tarfile, they may inadvertantly get ours.
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

    if not hasattr(tarfile.TarInfo, '__slots__'):
        __slots__ = (
            "name", "mode", "uid", "gid", "size", "mtime", "chksum", "type",
            "linkname", "_uname", "_gname", "devmajor", "devminor", "prefix",
            "offset", "offset_data", "_buf", "sparse", "_link_target")
    else:
        __slots__ = ()

    def get_buf(self):
        return self.tobuf()

    def set_buf(self, val):
        pass

    def del_buf(self):
        pass

    buf = property(get_buf, set_buf, del_buf)


    def get_gname(self):
        return self._gname

    def set_gname(self, val):
        self._gname = intern(val)

    def del_gname(self):
        del self._gname

    gname = property(get_gname, set_gname)

    def get_uname(self):
        return self._uname

    def set_uname(self, val):
        self._uname = intern(val)

    def del_uname(self):
        del self._uname

    uname = property(get_uname, set_uname)


tarfile.TarInfo = TarInfo
# python 2.6
tarfile.TarFile.tarinfo = TarInfo
# finished monkey patching. now to lift things out of our tarfile
# module into this scope so from/import behaves properly.

for x in tarfile.__all__:
    locals()[x] = getattr(tarfile, x)
del x
