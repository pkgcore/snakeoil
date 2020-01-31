"""
A far more minimal form of file protocol encapsulation location and encoding into it

The primary use for data_source's is to encapsulate the following issues into a single object:

* is the data actually on disk (thus can I use more efficient ops against the file?).
* what is the preferred encoding?
* py3k compatibility concerns (bytes versus text file handles)

Note that all file like handles returned from `text_fileobj()` and `bytes_fileobj()`
have a required additional attribute- *exceptions*, either a single Exception class, or a
tuple of Exception classes that can be thrown by that file handle during usage.

This requirement exists purely to allow the consuming code to avoid having to know anything
about the backing of the file like object.

The proper way to use such a filehandle is as follows:

>>> from snakeoil.data_source import data_source
>>> source = data_source("It's a fez. I wear a fez now. Fezes are cool.", mutable=False)
>>> handle = source.text_fileobj()
>>> handle.write("You graffitied the oldest cliff face in the universe.")
Traceback (most recent call last):
TypeError:
>>> # if this where a normal file, it would be an IOError- it's impossible to guess the
>>> # correct exception to intercept, so instead we rely on the handle telling us what
>>> # we should catch;
>>> try:
...   handle.write("You wouldn't answer your phone.")
... except handle.exceptions as e:
...   print("we caught the exception.")
we caught the exception.
"""

__all__ = (
    "base", "bz2_source", "data_source", "local_source", "text_data_source",
    "bytes_data_source", "invokable_data_source",
)

import errno
from functools import partial

from . import compression, fileutils, klass, stringio
from .currying import post_curry


def _mk_writable_cls(base, name):
    """
    inline mixin of writable overrides

    while a normal mixin is preferable, this is required due to
    differing slot layouts between py2k/py3k base classes of
    stringio.
    """

    class kls(base):
        __doc__ = """
        writable %s StringIO instance suitable for usage as a data_source filehandle

        This adds a callback for updating the original data source, and appropriate
        exceptions attribute
        """ % (name.split("_")[0],)


        base_cls = base
        exceptions = (MemoryError,)
        __slots__ = ('_callback',)

        def __init__(self, callback, data):
            """
            :param callback: functor invoked when this data source is modified;
                the functor takes a single value, the full content of the StringIO
            :param data: initial data for this instance
            """
            if not callable(callback):
                raise TypeError("callback must be callable")
            self.base_cls.__init__(self, data)
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
    """
    readonly text mode StringIO usable as a filehandle for a data_source

    Specifically this adds the necessary `exceptions` attribute; see
    :py:class:`snakeoil.stringio.text_readonly` for methods details.
    """
    __slots__ = ()
    exceptions = (MemoryError, TypeError)


class bytes_ro_StringIO(stringio.bytes_readonly):
    """
    readonly bytes mode StringIO usable as a filehandle for a data_source

    Specifically this adds the necessary `exceptions` attribute; see
    :py:class:`snakeoil.stringio.bytes_readonly` for methods details.
    """
    __slots__ = ()
    exceptions = (MemoryError, TypeError)


# derive our file classes- we derive *strictly* to append
# the exceptions class attribute for consumer usage.
def open_file(*args, **kwds):
    handle = open(*args, **kwds)
    handle.exceptions = (EnvironmentError,)
    return handle


class base:
    """
    base data_source class; implementations of the protocol are advised
    to derive from this.

    :ivar path: If None, no local path is available- else it's the ondisk path to
      the data
    """
    __slots__ = ("weakref",)

    path = None

    def text_fileobj(self, writable=False):
        """get a text level filehandle for for this data

        :param writable: whether or not we need to write to the handle
        :raise: TypeError if immutable and write is requested
        :return: file handle like object
        """
        raise NotImplementedError(self, "text_fileobj")

    def bytes_fileobj(self, writable=False):
        """get a bytes level filehandle for for this data

        :param writable: whether or not we need to write to the handle
        :raise: TypeError if immutable and write is requested
        :return: file handle like object
        """
        raise NotImplementedError(self, "bytes_fileobj")

    def transfer_to_path(self, path):
        return self.transfer_to_data_source(
            local_source(path, mutable=True, encoding=None))

    def transfer_to_data_source(self, write_source):
        read_f, m, write_f = None, None, None
        try:
            write_f = write_source.bytes_fileobj(True)
            if self.path is not None:
                m, read_f = fileutils.mmap_or_open_for_read(self.path)
            else:
                read_f = self.bytes_fileobj()

            if read_f is not None:
                transfer_between_files(read_f, write_f)
            else:
                write_f.write(m)
        finally:
            for x in (read_f, write_f, m):
                if x is None:
                    continue
                try:
                    x.close()
                except EnvironmentError:
                    pass


class local_source(base):

    """locally accessible data source

    Literally a file on disk.
    """

    __slots__ = ("path", "mutable", "encoding")

    buffering_window = 32768

    def __init__(self, path, mutable=False, encoding=None):
        """
        :param path: file path of the data source
        :param mutable: whether this data_source is considered modifiable or not
        :param encoding: the text encoding to force, if any
        """
        base.__init__(self)
        self.path = path
        self.mutable = mutable
        self.encoding = encoding

    @klass.steal_docs(base)
    def text_fileobj(self, writable=False):
        if writable and not self.mutable:
            raise TypeError("data source %s is immutable" % (self,))
        if self.encoding:
            opener = open_file
            opener = post_curry(opener, buffering=self.buffering_window,
                                encoding=self.encoding)
        else:
            opener = post_curry(open_file, self.buffering_window)
        if not writable:
            return opener(self.path, 'r')
        try:
            return opener(self.path, "r+")
        except IOError as ie:
            if ie.errno != errno.ENOENT:
                raise
            return opener(self.path, 'w+')

    @klass.steal_docs(base)
    def bytes_fileobj(self, writable=False):
        if not writable:
            return open_file(self.path, 'rb', self.buffering_window)
        if not self.mutable:
            raise TypeError("data source %s is immutable" % (self,))
        try:
            return open_file(self.path, 'rb+', self.buffering_window)
        except IOError as ie:
            if ie.errno != errno.ENOENT:
                raise
            return open_file(self.path, 'wb+', self.buffering_window)


class bz2_source(base):
    """
    locally accessible bz2 archive

    Literally a bz2 file on disk.
    """

    __slots__ = ("path", "mutable")

    def __init__(self, path, mutable=False):
        """
        :param path: file path of the data source
        :param mutable: whether this data source is considered modifiable or not
        """
        base.__init__(self)
        self.path = path
        self.mutable = mutable

    def text_fileobj(self, writable=False):
        data = compression.decompress_data(
            'bzip2', fileutils.readfile_bytes(self.path)).decode()
        if writable:
            if not self.mutable:
                raise TypeError("data source %s is not mutable" % (self,))
            return text_wr_StringIO(self._set_data, data)
        return text_ro_StringIO(data)

    def bytes_fileobj(self, writable=False):
        data = compression.decompress_data(
            'bzip2', fileutils.readfile_bytes(self.path))
        if writable:
            if not self.mutable:
                raise TypeError("data source %s is not mutable" % (self,))
            return bytes_wr_StringIO(self._set_data, data)
        return bytes_ro_StringIO(data)

    def _set_data(self, data):
        if isinstance(data, str):
            data = data.encode()
        with open(self.path, "wb") as f:
            f.write(compression.compress_data('bzip2', data))


class data_source(base):

    """
    base class encapsulating a purely virtual data source lacking an on disk location.

    Whether this be due to transformation steps necessary (pulling the data out of
    an archive for example), or the data being generated on the fly, this classes's
    derivatives :py:class:`text_data_source` and :py:class:`bytes_data_source` are
    likely what you should be using for direct creation.

    :ivar data: the raw data- should either be a string or bytes depending on your
      derivative
    :ivar path: note that path is None for this class- no on disk location available.
    """

    __slots__ = ('data', 'mutable')

    def __init__(self, data, mutable=False):
        """
        :param data: data to wrap
        :param mutable: should this data_source be updatable?
        """
        base.__init__(self)
        self.data = data
        self.mutable = mutable

    def _convert_data(self, mode):
        if mode == 'bytes':
            if isinstance(self.data, bytes):
                return self.data
            return self.data.encode()
        if isinstance(self.data, str):
            return self.data
        return self.data.decode()

    @klass.steal_docs(base)
    def text_fileobj(self, writable=False):
        if writable:
            if not self.mutable:
                raise TypeError("data source %s is not mutable" % (self,))
            return text_wr_StringIO(self._reset_data,
                                    self._convert_data('text'))
        return text_ro_StringIO(self._convert_data('text'))

    def _reset_data(self, data):
        if isinstance(self.data, bytes):
            if not isinstance(data, bytes):
                data = data.encode()
        elif not isinstance(data, str):
            data = data.decode()
        self.data = data

    @klass.steal_docs(base)
    def bytes_fileobj(self, writable=False):
        if writable:
            if not self.mutable:
                raise TypeError("data source %s is not mutable" % (self,))
            return bytes_wr_StringIO(self._reset_data,
                                     self._convert_data('bytes'))
        return bytes_ro_StringIO(self._convert_data('bytes'))


class text_data_source(data_source):
    """Text data source.

    This does autoconversionbetween bytes/text as needed.
    """

    __slots__ = ()

    @klass.steal_docs(data_source)
    def __init__(self, data, mutable=False):
        if not isinstance(data, str):
            raise TypeError("data must be a str")
        data_source.__init__(self, data, mutable=mutable)

    def _convert_data(self, mode):
        if mode != 'bytes':
            return self.data
        return self.data.encode()


class bytes_data_source(data_source):
    """Bytes data source.

    This does autoconversion between bytes/text as needed.
    """

    __slots__ = ()

    @klass.steal_docs(data_source)
    def __init__(self, data, mutable=False):
        if not isinstance(data, bytes):
            raise TypeError("data must be bytes")
        data_source.__init__(self, data, mutable=mutable)

    def _convert_data(self, mode):
        if mode == 'bytes':
            return self.data
        return self.data.decode()


class invokable_data_source(data_source):

    """
    data source that takes a callable instead of the actual data item

    The callable takes a single argument- a boolean, True if a text fileobj
    is requested, False if None

    Note that this instance is explicitly readonly.
    """
    __slots__ = ()

    def __init__(self, data):
        """
        :param data: callable that accepts one argument- True if a text
          file obj was requested, False if a bytes file obj is requested.
        """
        data_source.__init__(self, data, mutable=False)

    @klass.steal_docs(data_source)
    def text_fileobj(self, writable=False):
        if writable:
            raise TypeError("data source %s data is immutable" % (self,))
        return self.data(True)

    @klass.steal_docs(data_source)
    def bytes_fileobj(self, writable=False):
        if writable:
            raise TypeError("data source %s data is immutable" % (self,))
        return self.data(False)

    @classmethod
    def wrap_function(cls, invokable, returns_text=True, returns_handle=False, encoding_hint=None):
        """
        Helper function to automatically convert a function that returns text or bytes into appropriate
        callable

        :param invokable: a callable that returns either text, or bytes, taking no args
        :param returns_text: True if the data returned is text/basestring, False if Not
        :param returns_handle: True if the object returned is a handle, False if not.  Note that returns_text
            still has meaning here- returns_text indicates what sort of data the handle returns from read
            invocations.
        :param encoding_hint: the preferred encoding to use for encoding
        :return: invokable_data_source instance
        """
        return cls(partial(cls._simple_wrapper, invokable, encoding_hint, returns_text, returns_handle))

    @staticmethod
    def _simple_wrapper(invokable, encoding_hint, returns_text, returns_handle, text_wanted):
        data = invokable()
        if returns_text != text_wanted:
            if text_wanted:
                if returns_handle:
                    data = data.read()
                if encoding_hint:
                    # we have an encoding, its bytes data, and text is wanted
                    data = data.decode(encoding_hint)
                else:
                    data = data.decode()
            else:
                # bytes were wanted...
                if returns_handle:
                    # pull in the data...
                    data = data.read()
                if encoding_hint is None:
                    # fallback to utf8
                    encoding_hint = 'utf8'
                data = data.encode(encoding_hint)
        elif returns_handle:
            return data
        if text_wanted:
            return text_ro_StringIO(data)
        return bytes_ro_StringIO(data)


def transfer_between_files(read_file, write_file, bufsize=(32 * 1024)):
    data = read_file.read(bufsize)
    while data:
        write_file.write(data)
        data = read_file.read(bufsize)
