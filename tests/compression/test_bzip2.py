import importlib
from bz2 import decompress

import pytest
from snakeoil.compression import _bzip2
from snakeoil.process import CommandNotFound, find_binary
from snakeoil.test import hide_imports

from . import Base, hide_binary


def test_no_native():
    with hide_imports('bz2'):
        importlib.reload(_bzip2)
        assert not _bzip2.native


def test_missing_bzip2_binary():
    with hide_binary('bzip2'):
        with pytest.raises(CommandNotFound, match='bzip2'):
            importlib.reload(_bzip2)


def test_missing_lbzip2_binary():
    with hide_binary('lbzip2'):
        importlib.reload(_bzip2)
        assert not _bzip2.parallelizable

class Bzip2Base(Base):

    module = 'bzip2'
    decompressed_test_data = b'Some text here\n'
    compressed_test_data = (
        b'BZh91AY&SY\x1bM\x00\x02\x00\x00\x01\xd3\x80\x00\x10@\x00\x08\x00\x02'
        b'B\x94@ \x00"\r\x03\xd4\x0c \t!\x1b\xb7\x80u/\x17rE8P\x90\x1bM\x00\x02'
    )

    def decompress(self, data: bytes) -> bytes:
        return decompress(data)


class TestStdlib(Bzip2Base):

    @pytest.fixture(autouse=True, scope='class')
    def _setup(self):
        try:
            find_binary('bzip2')
        except CommandNotFound:
            pytest.skip('bzip2 binary not found')
        with hide_binary('lbzip2'):
            importlib.reload(_bzip2)
            yield


class TestBzip2(Bzip2Base):

    @pytest.fixture(autouse=True, scope='class')
    def _setup(self):
        with hide_binary('lbzip2'):
            importlib.reload(_bzip2)
            yield


class TestLbzip2(Bzip2Base):

    @pytest.fixture(autouse=True, scope='class')
    def _setup(self):
        try:
            find_binary('lbzip2')
        except CommandNotFound:
            pytest.skip('lbzip2 binary not found')
        importlib.reload(_bzip2)

    def test_bad_level(self):
        with pytest.raises(ValueError, match='unknown option "-0"'):
            _bzip2.compress_data(self.decompressed_test_data, level=90, parallelize=True)
