# Copyright: 2010 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD 3 clause

__all__ = ('text_readonly', 'text_writable', 'bytes_readonly', 'bytes_writable')

from snakeoil import compatibility, currying

def _generic_immutable_method(attr, self, *a, **kwds):
    raise TypeError("%s isn't opened for writing" % (self,))

def _make_ro_cls(base_cls, name):
    class kls(base_cls):
        __slots__ = ()
        locals().update((k, currying.pre_curry(_generic_immutable_method, k))
            for k in ["write", "writelines", "truncate"])
    kls.__name__ = name
    return kls


if compatibility.is_py3k:
    import io
    text_writable = io.StringIO
    bytes_writable = io.BytesIO
    text_readonly = _make_ro_cls(io.StringIO, 'text_readonly')
    bytes_readonly = _make_ro_cls(io.BytesIO, 'bytes_readonly')

else:
    from StringIO import StringIO as text_writable
    bytes_writable = text_writable

    try:
        from cStringIO import StringIO as text_readonly
    except ImportError:
        text_readonly = text_writable
    # note that we rewrite both classes... this is due to cStringIO allowing
    # truncate to still modify the data.
    text_readonly = _make_ro_cls(text_writable, 'text_readonly')
    bytes_readonly = text_readonly
