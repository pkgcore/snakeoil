# Copyright: 2005-2008 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD

"""
data source.

Think of it as a far more minimal form of file protocol
"""

__all__ = ("base", "data_source", "local_source", "text_data_source",
    "bytes_data_source")

from snakeoil.currying import (pre_curry, alias_class_method, post_curry,
    pretty_docs, alias_class_method)
from snakeoil import compatibility, demandload, stringio
demandload.demandload(globals(), 'codecs')

def _mk_writable_cls(base, name):
    """
    inline mixin of writable overrides

    while a normal mixin is preferable, this is required due to
    differing slot layouts between py2k/py3k base classes of
    stringio.
    """

    class kls(base):

        base_cls = base
        exceptions = (MemoryError,)
        __slots__ = ('_callback',)

        def __init__(self, callback, *args, **kwds):
            if not callable(callback):
                raise TypeError("callback must be callable")
            self.base_cls.__init__(self, *args, **kwds)
            self._callback = callback

        def close(self):
            self.flush()
            if self._callback is not None:
                self.seek(0)
                self._callback(self.read())
                self._callback = None
            self.base_cls.close(self)
    kls.__name__ = name
    return kls


text_wr_StringIO = _mk_writable_cls(stringio.text_writable, "text_wr_StringIO")
bytes_wr_StringIO = _mk_writable_cls(stringio.bytes_writable, "bytes_wr_StringIO")


class text_ro_StringIO(stringio.text_readonly):
    __slots__ = ()
    exceptions = (MemoryError, TypeError)


class bytes_ro_StringIO(stringio.bytes_readonly):
    __slots__ = ()
    exceptions = (MemoryError, TypeError)


# derive our file classes- we derive *strictly* to append
# the exceptions class attribute for consumer usage.
if compatibility.is_py3k:

    import io

    def open_file(*args, **kwds):
        handle = io.open(*args, **kwds)
        handle.exceptions = (EnvironmentError,)
        return handle

else:
    # have to derive since you can't modify file objects in py2k
    class open_file(file):
        __slots__ = ()
        exceptions = (EnvironmentError,)


class base(object):
    """base class, all implementations should match this protocol"""

    __slots__ = ("weakref",)

    text_fileobj = bytes_fileobj = get_path = path = None

    get_fileobj = alias_class_method("text_fileobj", "get_fileobj",
        "deprecated; use get_text_fileobj instead")

    get_text_fileobj = alias_class_method("text_fileobj")
    get_bytes_fileobj = alias_class_method("bytes_fileobj")


class local_source(base):

    """locally accessible data source"""

    __slots__ = ("path", "mutable", "encoding")

    buffering_window = 32768

    def __init__(self, path, mutable=False, encoding=None):
        """@param path: file path of the data source"""
        base.__init__(self)
        self.path = path
        self.mutable = mutable
        self.encoding = encoding

    def get_path(self):
        return self.path

    def text_fileobj(self, writable=False):
        if writable and not self.mutable:
            raise TypeError("data source %s is immutable" % (self,))
        if self.encoding:
            opener = open_file
            if not compatibility.is_py3k:
                opener = codecs.open
            opener = post_curry(opener, buffering=self.buffering_window,
                encoding=self.encoding)
        else:
            opener = post_curry(open_file, self.buffering_window)
        if writable:
            return opener(self.path, "r+")
        return opener(self.path, "r")

    def bytes_fileobj(self, writable=False):
        if writable:
            if not self.mutable:
                raise TypeError("data source %s is immutable" % (self,))
            return open_file(self.path, "rb+", self.buffering_window)
        return open_file(self.path, 'rb', self.buffering_window)


class data_source(base):

    __slots__ = ('data', 'mutable')

    def __init__(self, data, mutable=False):
        """@param data: data to wrap"""
        base.__init__(self)
        self.data = data
        self.mutable = mutable

    if compatibility.is_py3k:
        def _convert_data(self, mode):
            if mode == 'bytes':
                if isinstance(self.data, bytes):
                    return self.data
                return self.data.encode()
            if isinstance(self.data, str):
                return self.data
            return self.data.decode()
    else:
        def _convert_data(self, mode):
            return self.data

    def text_fileobj(self, writable=False):
        if writable:
            if not self.mutable:
                raise TypeError("data source %s is not mutable" % (self,))
            return text_wr_StringIO(self._reset_data,
                self._convert_data('text'))
        return text_ro_StringIO(self._convert_data('text'))

    if compatibility.is_py3k:
        def _reset_data(self, data):
            if isinstance(self.data, bytes):
                if not isinstance(data, bytes):
                    data = data.encode()
            elif not isinstance(data, str):
                data = data.decode()
            self.data = data
    else:
        def _reset_data(self, data):
            self.data = data

    def bytes_fileobj(self, writable=False):
        if writable:
            if not self.mutable:
                raise TypeError("data source %s is not mutable" % (self,))
            return bytes_wr_StringIO(self._reset_data,
                self._convert_data('bytes'))
        return bytes_ro_StringIO(self._convert_data('bytes'))


if not compatibility.is_py3k:
    text_data_source = data_source
    bytes_data_source = data_source
else:
    class text_data_source(data_source):

        __slots__ = ()

        def __init__(self, data, mutable=False):
            if not isinstance(data, str):
                raise TypeError("data must be a str")
            data_source.__init__(self, data, mutable=mutable)

        def _convert_data(self, mode):
            if mode != 'bytes':
                return self.data
            return self.data.encode()

    class bytes_data_source(data_source):

        __slots__ = ()

        def __init__(self, data, mutable=False):
            if not isinstance(data, bytes):
                raise TypeError("data must be bytes")
            data_source.__init__(self, data, mutable=mutable)

        def _convert_data(self, mode):
            if mode == 'bytes':
                return self.data
            return self.data.decode()

def transfer_data(read_fsobj, write_fsobj, bufsize=(4096 * 16)):
    data = read_fsobj.read(bufsize)
    while data:
        write_fsobj.write(data)
        data = read_fsobj.read(bufsize)
