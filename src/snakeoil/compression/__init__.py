import multiprocessing
import shlex
import subprocess
from contextlib import contextmanager
from functools import cached_property
from importlib import import_module

from .. import process
from ..cli.exceptions import UserException


class _transform_source:
    def __init__(self, name):
        self.name = name

    @cached_property
    def module(self):
        return import_module(f"snakeoil.compression._{self.name}")

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


_transforms = {name: _transform_source(name) for name in ("bzip2", "xz")}


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


def _exit_code(returncode: int) -> int:
    """Normalize a :py:mod:`subprocess` return code into a shell exit status."""
    if returncode < 0:
        # died from a signal, which subprocess reports as its negation; use the
        # shell's 128+signal convention so the code stays a positive status
        return 128 - returncode
    return returncode


class ArComp:
    """Generic archive and compressed file format support."""

    binary: tuple[str, ...]
    default_unpack_cmd: str
    exts: frozenset[str] = frozenset()
    known_exts = {}

    def __new__(cls, *args, ext, **kwargs):
        try:
            cls = cls.known_exts[ext]
            return super().__new__(cls)
        except KeyError:
            raise ArCompError(f"unknown compression file extension: {ext!r}")

    def __init_subclass__(cls, **kwargs):
        """Initialize result subclasses and register archive extensions."""
        super().__init_subclass__(**kwargs)
        if not all((cls.binary, cls.default_unpack_cmd, cls.exts)):
            raise ValueError(f"class missing required attrs: {cls!r}")
        if cls._streams is ArComp._streams:
            raise ValueError(f"class does not implement _streams: {cls!r}")
        for ext in cls.exts:
            cls.known_exts[ext] = cls

    def __init__(self, path, ext=None):
        self.path = path

    @cached_property
    def _unpack_cmd(self):
        for b in self.binary:
            try:
                binary = process.find_binary(b)
                break
            except process.CommandNotFound:
                continue
        else:
            choices = ", ".join(self.binary)
            raise ArCompError(
                f"required binary not found from the following choices: {choices}"
            )
        cmd = self.default_unpack_cmd.format(binary=binary, path=self.path)
        return cmd

    @contextmanager
    def _streams(self, dest):
        """Yield the (stdin, stdout) the unpack command runs with."""
        raise NotImplementedError

    def unpack(self, dest=None, *, user=None, group=None):
        """Unpack :py:attr:`path`.

        :param dest: where the decompressed data lands; archive formats ignore
            it and unpack into the current directory.
        :param user: run the unpack command as this user, see
            :py:class:`subprocess.Popen`.
        :param group: run the unpack command as this group.
        :raise ArCompError: if the unpack command is unavailable or fails.
        """
        # resolve the command first; a missing binary must not leave an empty
        # dest behind
        cmd = shlex.split(self._unpack_cmd)
        with self._streams(dest) as (stdin, stdout):
            ret = subprocess.run(
                cmd,
                stdin=stdin,
                stdout=stdout,
                stderr=subprocess.PIPE,
                user=user,
                group=group,
                check=False,
            )
        if ret.returncode:
            msg = (ret.stderr or b"").decode("utf-8", "replace").strip()
            raise ArCompError(
                msg or f"unpacking failed: {self.path!r}",
                code=_exit_code(ret.returncode),
            )


class _Archive:
    """Generic archive format support."""

    @contextmanager
    def _streams(self, dest):
        yield None, subprocess.DEVNULL


class _CompressedFile:
    """Single compressed file."""

    @contextmanager
    def _streams(self, dest):
        with open(dest, "wb") as f:
            yield subprocess.DEVNULL, f


class _CompressedStdin:
    """Compressed data from stdin."""

    @contextmanager
    def _streams(self, dest):
        with open(self.path, "rb") as src, open(dest, "wb") as f:
            yield src, f


class _Tar(_Archive, ArComp):
    exts = frozenset([".tar"])
    binary = ("gtar", "tar")
    compress_binary: tuple[tuple[str, ...], ...] | None = None
    default_unpack_cmd = '{binary} xf "{path}"'

    @cached_property
    def _unpack_cmd(self):
        cmd = super()._unpack_cmd
        if self.compress_binary is not None:
            for b in self.compress_binary:
                try:
                    process.find_binary(b[0])
                    # FIXME: This is a gnuism, needs gnu tar.
                    cmd += f' --use-compress-program="{" ".join(b)}"'
                    break
                except process.CommandNotFound:
                    pass
            else:
                choices = ", ".join(next(zip(*self.compress_binary)))
                raise ArCompError(
                    f"no compression binary found from the following choices: {choices}"
                )
        return cmd


class _TarGZ(_Tar):
    exts = frozenset([".tar.gz", ".tgz", ".tar.Z", ".tar.z"])
    compress_binary = (("pigz",), ("gzip",))


class _TarBZ2(_Tar):
    exts = frozenset([".tar.bz2", ".tbz2", ".tbz"])
    compress_binary = (("lbzip2",), ("pbzip2",), ("bzip2",))


class _TarLZMA(_Tar):
    exts = frozenset([".tar.lzma"])
    compress_binary = (("lzma",),)


class _TarXZ(_Tar):
    exts = frozenset([".tar.xz", ".txz"])
    compress_binary = (("pixz",), ("xz", f"-T{multiprocessing.cpu_count()}"))


class _Zip(_Archive, ArComp):
    exts = frozenset([".ZIP", ".zip", ".jar"])
    binary = ("unzip",)
    default_unpack_cmd = '{binary} -qo "{path}"'


class _GZ(_CompressedStdin, ArComp):
    exts = frozenset([".gz", ".Z", ".z"])
    binary = ("pigz", "gzip")
    default_unpack_cmd = "{binary} -d -c"


class _BZ2(_CompressedStdin, ArComp):
    exts = frozenset([".bz2", ".bz"])
    binary = ("lbzip2", "pbzip2", "bzip2")
    default_unpack_cmd = "{binary} -d -c"


class _XZ(_CompressedStdin, ArComp):
    exts = frozenset([".xz"])
    binary = ("pixz", "xz")
    default_unpack_cmd = "{binary} -d -c"


class _7Z(_Archive, ArComp):
    exts = frozenset([".7Z", ".7z"])
    binary = ("7z",)
    default_unpack_cmd = '{binary} x -y "{path}"'


class _Rar(_Archive, ArComp):
    exts = frozenset([".RAR", ".rar"])
    binary = ("unrar",)
    default_unpack_cmd = '{binary} x -idq -o+ "{path}"'


class _LHA(_Archive, ArComp):
    exts = frozenset([".LHa", ".LHA", ".lha", ".lzh"])
    binary = ("lha",)
    default_unpack_cmd = '{binary} xfq "{path}"'


class _Ar(_Archive, ArComp):
    exts = frozenset([".a", ".deb"])
    binary = ("ar",)
    default_unpack_cmd = '{binary} x "{path}"'


class _LZMA(_CompressedFile, ArComp):
    exts = frozenset([".lzma"])
    binary = ("lzma",)
    default_unpack_cmd = '{binary} -dc "{path}"'
