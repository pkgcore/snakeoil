import shutil
import subprocess
import sys

import pytest
from snakeoil.compression import ArComp, ArCompError, _TarBZ2
from snakeoil.contexts import chdir

from . import hide_binary


@pytest.mark.skipif(sys.platform == "darwin", reason="darwin fails with bzip2")
class TestArComp:

    @pytest.fixture(scope='class')
    def tar_file(self, tmp_path_factory):
        data = tmp_path_factory.mktemp("data")
        (data / 'file1').write_text('Hello world')
        (data / 'file2').write_text('Larry the Cow')
        path = data / 'test 1.tar'
        subprocess.run(['tar', 'cf', str(path), 'file1', 'file2'], cwd=data, check=True)
        (data / 'file1').unlink()
        (data / 'file2').unlink()
        return str(path)

    @pytest.fixture(scope='class')
    def tar_bz2_file(self, tar_file):
        subprocess.run(['bzip2', '-z', '-k', tar_file], check=True)
        return tar_file + ".bz2"

    @pytest.fixture(scope='class')
    def tbz2_file(self, tar_bz2_file):
        new_path = tar_bz2_file.replace('.tar.bz2', '.tbz2')
        shutil.copyfile(tar_bz2_file, new_path)
        return new_path

    @pytest.fixture(scope='class')
    def lzma_file(self, tmp_path_factory):
        data = (tmp_path_factory.mktemp("data") / 'test 2.lzma')
        with data.open('wb') as f:
            subprocess.run(['lzma'], check=True, input=b'Hello world', stdout=f)
        return str(data)

    def test_unknown_extenstion(self, tmp_path):
        file = tmp_path / 'test.file'
        with pytest.raises(ArCompError, match='unknown compression file extension'):
            ArComp(file, ext='.foo')

    def test_missing_tar(self, tmp_path, tar_file):
        with hide_binary('tar'), chdir(tmp_path):
            with pytest.raises(ArCompError, match='required binary not found'):
                ArComp(tar_file, ext='.tar').unpack(dest=tmp_path)

    def test_tar(self, tmp_path, tar_file):
        with chdir(tmp_path):
            ArComp(tar_file, ext='.tar').unpack(dest=tmp_path)
        assert (tmp_path / 'file1').read_text() == 'Hello world'
        assert (tmp_path / 'file2').read_text() == 'Larry the Cow'

    def test_tar_bz2(self, tmp_path, tar_bz2_file):
        with chdir(tmp_path):
            ArComp(tar_bz2_file, ext='.tar.bz2').unpack(dest=tmp_path)
        assert (tmp_path / 'file1').read_text() == 'Hello world'
        assert (tmp_path / 'file2').read_text() == 'Larry the Cow'

    def test_tbz2(self, tmp_path, tbz2_file):
        with chdir(tmp_path):
            ArComp(tbz2_file, ext='.tbz2').unpack(dest=tmp_path)
        assert (tmp_path / 'file1').read_text() == 'Hello world'
        assert (tmp_path / 'file2').read_text() == 'Larry the Cow'

    def test_fallback_tbz2(self, tmp_path, tbz2_file):
        with hide_binary(*next(zip(*_TarBZ2.compress_binary[:-1]))):
            with chdir(tmp_path):
                ArComp(tbz2_file, ext='.tbz2').unpack(dest=tmp_path)
            assert (tmp_path / 'file1').read_text() == 'Hello world'
            assert (tmp_path / 'file2').read_text() == 'Larry the Cow'

    def test_no_fallback_tbz2(self, tmp_path, tbz2_file):
        with hide_binary(*next(zip(*_TarBZ2.compress_binary))), chdir(tmp_path):
            with pytest.raises(ArCompError, match='no compression binary'):
                ArComp(tbz2_file, ext='.tbz2').unpack(dest=tmp_path)

    def test_lzma(self, tmp_path, lzma_file):
        dest = tmp_path / 'file'
        with chdir(tmp_path):
            ArComp(lzma_file, ext='.lzma').unpack(dest=dest)
        assert (dest).read_bytes() == b'Hello world'
