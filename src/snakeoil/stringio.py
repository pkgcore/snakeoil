"""
StringIO functionality

This module provides essentially two types of StringIO's, and two types of modes
of operation; text versus bytes, and readonly versus writable.

The reason for separate classes is that when we're running on py2k, if all we're
doing is consuming/reading the data it's heavily preferable to use ``cStringIO.StringIO``
if at all possible for performance reasons.  Thus we have readonly and writable
classes; the separation has clear performance benefits.

Note that while this functionality is based on StringIO and friends, there is some
differences in behavior from stdlib- stdlib's ``cStringIO.StringIO`` is
pseudo-writable; it has a truncate method (which works).  This is suboptimal since
the majority of consumers treat it as write only, thus in these classes we specifically
raise a TypeError if you try to truncate a readonly instance.  Further, instead of
just lacking `write` and `writelines` methods, we supply those (to maintain file
like IO compatibility) but have them raise TypeError if invoked

Exempting the caveats above, usage of these classes is basically no different
than interacting with a normal StringIO.

Finally note that the __slots__ layout for py2k cStringIO differs from
io.BytesIO (or io.TextIO) in py3k; as such if you're deriving from a writable
instance you'll need to compensate for this if you want to have source that
is usable under both py2k and py3k.
"""

# TODO: deprecated, remove in 0.9.0
__all__ = ('text_readonly', 'bytes_readonly')

import io


def _generic_immutable_method(self, *a, **kwds):
    raise TypeError(f"{self} isn't opened for writing")


class _make_ro_cls(type):
    def __new__(cls, name, bases, dct):
        x = super().__new__(cls, name, bases, dct)
        for k in ("write", "writelines", "truncate"):
            setattr(x, k, _generic_immutable_method)
        return x


class text_readonly(io.StringIO, metaclass=_make_ro_cls):
    ...


class bytes_readonly(io.BytesIO, metaclass=_make_ro_cls):
    ...
