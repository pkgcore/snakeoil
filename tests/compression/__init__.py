from unittest.mock import patch

import pytest
from snakeoil import compression
from snakeoil.process import CommandNotFound, find_binary

def hide_binary(*binaries: str):
    def mock_find_binary(name):
        if name in binaries:
            raise CommandNotFound(name)
        return find_binary(name)

    return patch('snakeoil.process.find_binary', side_effect=mock_find_binary)


class Base:

    module: str = ''
    decompressed_test_data: bytes = b''
    compressed_test_data: bytes = b''

    def decompress(self, data: bytes) -> bytes:
        raise NotImplementedError(self, 'decompress')

    @pytest.mark.parametrize('parallelize', (True, False))
    @pytest.mark.parametrize('level', (1, 9))
    def test_compress_data(self, level, parallelize):
        compressed = compression.compress_data(self.module, self.decompressed_test_data, level=level, parallelize=parallelize)
        assert compressed
        assert self.decompress(compressed) == self.decompressed_test_data

    @pytest.mark.parametrize('parallelize', (True, False))
    def test_decompress_data(self, parallelize):
        assert self.decompressed_test_data == compression.decompress_data(self.module, self.compressed_test_data, parallelize=parallelize)

    @pytest.mark.parametrize('parallelize', (True, False))
    @pytest.mark.parametrize('level', (1, 9))
    def test_compress_handle(self, tmp_path, level, parallelize):
        path = tmp_path / f'test.{self.module}'

        stream = compression.compress_handle(self.module, str(path), level=level, parallelize=parallelize)
        stream.write(self.decompressed_test_data)
        stream.close()
        assert self.decompress(path.read_bytes()) == self.decompressed_test_data

        with path.open("wb") as file:
            stream = compression.compress_handle(self.module, file, level=level, parallelize=parallelize)
            stream.write(self.decompressed_test_data)
            stream.close()
            assert self.decompress(path.read_bytes()) == self.decompressed_test_data

        with path.open("wb") as file:
            stream = compression.compress_handle(self.module, file.fileno(), level=level, parallelize=parallelize)
            stream.write(self.decompressed_test_data)
            stream.close()
            assert self.decompress(path.read_bytes()) == self.decompressed_test_data

        with pytest.raises(TypeError):
            compression.compress_handle(self.module, b'', level=level, parallelize=parallelize)

    @pytest.mark.parametrize('parallelize', (True, False))
    def test_decompress_handle(self, tmp_path, parallelize):
        path = tmp_path / f'test.{self.module}'
        path.write_bytes(self.compressed_test_data)

        stream = compression.decompress_handle(self.module, str(path), parallelize=parallelize)
        assert stream.read() == self.decompressed_test_data
        stream.close()

        with path.open("rb") as file:
            stream = compression.decompress_handle(self.module, file, parallelize=parallelize)
            assert stream.read() == self.decompressed_test_data
            stream.close()

        with path.open("rb") as file:
            stream = compression.decompress_handle(self.module, file.fileno(), parallelize=parallelize)
            assert stream.read() == self.decompressed_test_data
            stream.close()

        with pytest.raises(TypeError):
            compression.decompress_handle(self.module, b'', parallelize=parallelize)
