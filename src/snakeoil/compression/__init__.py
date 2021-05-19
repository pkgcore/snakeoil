import shlex
from importlib import import_module

from .. import klass
from ..cli.exceptions import UserException
from ..process import CommandNotFound, find_binary
from ..process.spawn import spawn_get_output


class _transform_source:

    def __init__(self, name):
        self.name = name

    @klass.jit_attr
    def module(self):
        return import_module(f'snakeoil.compression._{self.name}')

    @klass.jit_attr
    def parallelizable(self):
        return bool(getattr(self.module, 'parallelizable', False))

    def compress_data(self, data, level, parallelize=False):
        parallelize = parallelize and self.module.parallelizable
        return self.module.compress_data(data, level, parallelize=parallelize)

    def decompress_data(self, data, parallelize=False):
        parallelize = parallelize and self.module.parallelizable
        return self.module.decompress_data(data, parallelize=parallelize)

    def compress_handle(self, handle, level, parallelize=False):
        parallelize = parallelize and self.module.parallelizable
        return self.module.compress_handle(handle, level, parallelize=parallelize)

    def decompress_handle(self, handle, parallelize=False):
        parallelize = parallelize and self.module.parallelizable
        return self.module.decompress_handle(handle, parallelize=parallelize)


_transforms = {name: _transform_source(name) for name in ('bzip2',)}


def compress_data(compressor_type, data, level=9, **kwds):
    return _transforms[compressor_type].compress_data(data, level, **kwds)


def decompress_data(compressor_type, data, **kwds):
    return _transforms[compressor_type].decompress_data(data, **kwds)


def compress_handle(compressor_type, handle, level=9, **kwds):
    return _transforms[compressor_type].compress_handle(handle, level, **kwds)


def decompress_handle(compressor_type, source, **kwds):
    return _transforms[compressor_type].decompress_handle(source, **kwds)


class ArCompError(UserException):
    """Generic archive and compressed file error."""

    def __init__(self, msg, code=-1):
        super().__init__(msg)
        self.code = code


class ArComp:
    """Generic archive and compressed file format support."""

    binary = None
    default_unpack_cmd = None
    known_exts = {}

    def __new__(cls, *args, ext, **kwargs):
        try:
            cls = cls.known_exts[ext]
            return super(ArComp, cls).__new__(cls)
        except KeyError:
            raise ArCompError(f'unknown compression file extension: {ext!r}')

    def __init_subclass__(cls, **kwargs):
        """Initialize result subclasses and register archive extensions."""
        super().__init_subclass__(**kwargs)
        if not all((cls.binary, cls.default_unpack_cmd, cls.exts)):
            raise ValueError(f'class missing required attrs: {cls!r}')
        for ext in cls.exts:
            cls.known_exts[ext] = cls

    def __init__(self, path, ext=None):
        self.path = path

    @klass.jit_attr
    def _unpack_cmd(self):
        for b in self.binary:
            try:
                binary = find_binary(b)
                break
            except CommandNotFound:
                continue
        else:
            choices = ', '.join(self.binary)
            raise ArCompError(
                f'required binary not found from the following choices: {choices}')
        cmd = self.default_unpack_cmd.format(binary=binary, path=self.path)
        return cmd

    def unpack(self, dest=None, **kwargs):
        raise NotImplementedError

    def create(self, dest):
        raise NotImplementedError


class _Archive:
    """Generic archive format support."""

    def unpack(self, dest=None, **kwargs):
        cmd = shlex.split(self._unpack_cmd.format(path=self.path))
        ret, output = spawn_get_output(cmd, collect_fds=(2,), **kwargs)
        if ret:
            msg = '\n'.join(output) if output else f'unpacking failed: {self.path!r}'
            raise ArCompError(msg, code=ret)


class _CompressedFile:
    """Single compressed file."""

    def unpack(self, dest=None, **kwargs):
        cmd = shlex.split(self._unpack_cmd.format(path=self.path))
        with open(dest, 'wb') as f:
            ret, output = spawn_get_output(
                cmd, collect_fds=(2,), fd_pipes={1: f.fileno()}, **kwargs)
        if ret:
            msg = '\n'.join(output) if output else f'unpacking failed: {self.path!r}'
            raise ArCompError(msg, code=ret)


class _CompressedStdin:
    """Compressed data from stdin."""

    def unpack(self, dest=None, **kwargs):
        cmd = shlex.split(self._unpack_cmd)
        with open(self.path, 'rb') as src, open(dest, 'wb') as f:
            ret, output = spawn_get_output(
                cmd, collect_fds=(2,), fd_pipes={0: src.fileno(), 1: f.fileno()}, **kwargs)
        if ret:
            msg = '\n'.join(output) if output else f'unpacking failed: {self.path!r}'
            raise ArCompError(msg, code=ret)


class _Tar(_Archive, ArComp):

    exts = frozenset(['.tar'])
    binary = ('tar',)
    compress_binary = None
    default_unpack_cmd = '{binary} xf "{path}"'

    @klass.jit_attr
    def _unpack_cmd(self):
        cmd = super()._unpack_cmd
        if self.compress_binary is not None:
            for b in self.compress_binary:
                try:
                    find_binary(b)
                    cmd += f' --use-compress-program={b}'
                    break
                except CommandNotFound:
                    pass
            else:
                choices = ', '.join(self.compress_binary)
                raise ArCompError(
                    'no compression binary found from the '
                    f'following choices: {choices}')
        return cmd


class _TarGZ(_Tar):

    exts = frozenset(['.tar.gz', '.tgz', '.tar.Z', '.tar.z'])
    compress_binary = ('pigz', 'gzip')


class _TarBZ2(_Tar):

    exts = frozenset(['.tar.bz2', '.tbz2', '.tbz'])
    compress_binary = ('lbzip2', 'pbzip2', 'bzip2')


class _TarLZMA(_Tar):

    exts = frozenset(['.tar.lzma'])
    compress_binary = ('lzma',)


class _TarXZ(_Tar):

    exts = frozenset(['.tar.xz', '.txz'])
    compress_binary = ('pixz', 'xz')


class _Zip(_Archive, ArComp):

    exts = frozenset(['.ZIP', '.zip', '.jar'])
    binary = ('unzip',)
    default_unpack_cmd = '{binary} -qo "{path}"'


class _GZ(_CompressedStdin, ArComp):

    exts = frozenset(['.gz', '.Z', '.z'])
    binary = ('pigz', 'gzip')
    default_unpack_cmd = '{binary} -d -c'


class _BZ2(_CompressedStdin, ArComp):

    exts = frozenset(['.bz2', '.bz'])
    binary = ('lbzip2', 'pbzip2', 'bzip2')
    default_unpack_cmd = '{binary} -d -c'


class _XZ(_CompressedStdin, ArComp):

    exts = frozenset(['.xz'])
    binary = ('pixz', 'xz')
    default_unpack_cmd = '{binary} -d -c'


class _7Z(_Archive, ArComp):

    exts = frozenset(['.7Z', '.7z'])
    binary = ('7z',)
    default_unpack_cmd = '{binary} x -y "{path}"'


class _Rar(_Archive, ArComp):

    exts = frozenset(['.RAR', '.rar'])
    binary = ('unrar',)
    default_unpack_cmd = '{binary} x -idq -o+ "{path}"'


class _LHA(_Archive, ArComp):

    exts = frozenset(['.LHa', '.LHA', '.lha', '.lzh'])
    binary = ('lha',)
    default_unpack_cmd = '{binary} xfq "{path}"'


class _Ar(_Archive, ArComp):

    exts = frozenset(['.a', '.deb'])
    binary = ('ar',)
    default_unpack_cmd = '{binary} x "{path}"'


class _LZMA(_CompressedFile, ArComp):

    exts = frozenset(['.lzma'])
    binary = ('lzma',)
    default_unpack_cmd = '{binary} -dc "{path}"'
