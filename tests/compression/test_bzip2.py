import importlib
from bz2 import decompress
from pathlib import Path
from unittest import mock

import pytest
from snakeoil.compression import _bzip2
from snakeoil.process import CommandNotFound, find_binary
from snakeoil.test import hide_imports


def hide_binary(*binaries: str):
    def mock_find_binary(name):
        if name in binaries:
            raise CommandNotFound(name)
        return find_binary(name)

    return mock.patch('snakeoil.process.find_binary', side_effect=mock_find_binary)


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


decompressed_test_data = b'Some text here\n'
compressed_test_data = (
    b'BZh91AY&SY\x1bM\x00\x02\x00\x00\x01\xd3\x80\x00\x10@\x00\x08\x00\x02'
    b'B\x94@ \x00"\r\x03\xd4\x0c \t!\x1b\xb7\x80u/\x17rE8P\x90\x1bM\x00\x02'
)


class Base:

    @pytest.mark.parametrize('parallelize', (True, False))
    @pytest.mark.parametrize('level', (1, 9))
    def test_compress_data(self, level, parallelize):
        compressed = _bzip2.compress_data(decompressed_test_data, level=level, parallelize=parallelize)
        assert compressed
        assert decompress(compressed) == decompressed_test_data

    @pytest.mark.parametrize('parallelize', (True, False))
    def test_decompress_data(self, parallelize):
        assert decompressed_test_data == _bzip2.decompress_data(compressed_test_data, parallelize=parallelize)

    @pytest.mark.parametrize('parallelize', (True, False))
    @pytest.mark.parametrize('level', (1, 9))
    def test_compress_handle(self, tmp_path, level, parallelize):
        path = tmp_path / 'test.bz2'

        stream = _bzip2.compress_handle(str(path), level=level, parallelize=parallelize)
        stream.write(decompressed_test_data)
        stream.close()
        assert decompress(path.read_bytes()) == decompressed_test_data

        with path.open("wb") as file:
            stream = _bzip2.compress_handle(file, level=level, parallelize=parallelize)
            stream.write(decompressed_test_data)
            stream.close()
            assert decompress(path.read_bytes()) == decompressed_test_data

        with path.open("wb") as file:
            stream = _bzip2.compress_handle(file.fileno(), level=level, parallelize=parallelize)
            stream.write(decompressed_test_data)
            stream.close()
            assert decompress(path.read_bytes()) == decompressed_test_data

        with pytest.raises(TypeError):
            _bzip2.compress_handle(b'', level=level, parallelize=parallelize)

    @pytest.mark.parametrize('parallelize', (True, False))
    def test_decompress_handle(self, tmp_path, parallelize):
        path: Path = tmp_path / 'test.bz2'
        path.write_bytes(compressed_test_data)

        stream = _bzip2.decompress_handle(str(path), parallelize=parallelize)
        assert stream.read() == decompressed_test_data
        stream.close()

        with path.open("rb") as file:
            stream = _bzip2.decompress_handle(file, parallelize=parallelize)
            assert stream.read() == decompressed_test_data
            stream.close()

        with path.open("rb") as file:
            stream = _bzip2.decompress_handle(file.fileno(), parallelize=parallelize)
            assert stream.read() == decompressed_test_data
            stream.close()

        with pytest.raises(TypeError):
            _bzip2.decompress_handle(b'', parallelize=parallelize)


class TestStdlib(Base):

    @pytest.fixture(autouse=True, scope='class')
    def _setup(self):
        try:
            find_binary('bzip2')
        except CommandNotFound:
            pytest.skip('bzip2 binary not found')
        with hide_binary('lbzip2'):
            importlib.reload(_bzip2)
            yield


class TestBzip2(Base):

    @pytest.fixture(autouse=True, scope='class')
    def _setup(self):
        with hide_binary('lbzip2'):
            importlib.reload(_bzip2)
            yield


class TestLbzip2(Base):

    @pytest.fixture(autouse=True, scope='class')
    def _setup(self):
        try:
            find_binary('lbzip2')
        except CommandNotFound:
            pytest.skip('lbzip2 binary not found')
        importlib.reload(_bzip2)

    def test_bad_level(self):
        with pytest.raises(ValueError, match='unknown option "-0"'):
            _bzip2.compress_data(decompressed_test_data, level=90, parallelize=True)
