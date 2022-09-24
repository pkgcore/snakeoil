import importlib
from lzma import decompress

import pytest
from snakeoil.compression import _xz
from snakeoil.process import CommandNotFound, find_binary
from snakeoil.test import hide_imports

from . import Base, hide_binary


def test_no_native():
    with hide_imports('lzma'):
        importlib.reload(_xz)
        assert not _xz.native


def test_missing_xz_binary():
    with hide_binary('xz'):
        with pytest.raises(CommandNotFound, match='xz'):
            importlib.reload(_xz)


class XzBase(Base):

    module = 'xz'
    decompressed_test_data = b'Some text here\n' * 2
    compressed_test_data = (
        b'\xfd7zXZ\x00\x00\x04\xe6\xd6\xb4F\x04\xc0\x1e\x1e!\x01\x16\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00j\xf6\x947\xe0\x00\x1d\x00\x16]\x00)\x9b\xc9\xa6g'
        b'Bw\x8c\xb3\x9eA\x9a\xbeT\xc9\xfa\xe3\x19\x8f(\x00\x00\x00\x00\x00\x96N'
        b'\xa8\x8ed\xa2WH\x00\x01:\x1e1V \xff\x1f\xb6\xf3}\x01\x00\x00\x00\x00\x04YZ'
    )

    def decompress(self, data: bytes) -> bytes:
        return decompress(data)


class TestStdlib(XzBase):

    @pytest.fixture(autouse=True, scope='class')
    def _setup(self):
        try:
            find_binary('xz')
        except CommandNotFound:
            pytest.skip('xz binary not found')
        importlib.reload(_xz)


class TestXz(XzBase):

    @pytest.fixture(autouse=True, scope='class')
    def _setup(self):
        with hide_imports('lzma'):
            importlib.reload(_xz)
            yield
