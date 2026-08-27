import os
import shutil
import subprocess
import sys
from contextlib import chdir

import pytest

from snakeoil.compression import ArComp, ArCompError, _Archive, _TarBZ2, _TarLZMA

from . import hide_binary


@pytest.mark.skipif(sys.platform == "darwin", reason="darwin fails with bzip2")
class TestArComp:
    @pytest.fixture(scope="class")
    def tar_file(self, tmp_path_factory):
        data = tmp_path_factory.mktemp("data")
        (data / "file1").write_text("Hello world")
        (data / "file2").write_text("Larry the Cow")
        path = data / "test 1.tar"
        subprocess.run(["tar", "cf", str(path), "file1", "file2"], cwd=data, check=True)
        (data / "file1").unlink()
        (data / "file2").unlink()
        return str(path)

    @pytest.fixture(scope="class")
    def tar_bz2_file(self, tar_file):
        subprocess.run(["bzip2", "-z", "-k", tar_file], check=True)
        return tar_file + ".bz2"

    @pytest.fixture(scope="class")
    def tbz2_file(self, tar_bz2_file):
        new_path = tar_bz2_file.replace(".tar.bz2", ".tbz2")
        shutil.copyfile(tar_bz2_file, new_path)
        return new_path

    @pytest.fixture(scope="class")
    def tar_lzma_file(self, tar_file):
        subprocess.run(["lzma", "-z", "-k", tar_file], check=True)
        return tar_file + ".lzma"

    @pytest.fixture(scope="class")
    def lzma_file(self, tmp_path_factory):
        data = tmp_path_factory.mktemp("data") / "test 2.lzma"
        with data.open("wb") as f:
            subprocess.run(["lzma"], check=True, input=b"Hello world", stdout=f)
        return str(data)

    @pytest.mark.parametrize(
        "attrs",
        (
            pytest.param({"binary": None}, id="binary"),
            pytest.param({"default_unpack_cmd": None}, id="default_unpack_cmd"),
            pytest.param({"exts": frozenset()}, id="exts"),
        ),
    )
    def test_subclass_missing_attrs(self, attrs):
        namespace = {
            "binary": ("nonexistent",),
            "default_unpack_cmd": "{binary}",
            "exts": frozenset([".test-missing-attrs"]),
            **attrs,
        }
        with pytest.raises(ValueError, match="missing required attrs"):
            type("Broken", (_Archive, ArComp), namespace)

    def test_subclass_missing_streams(self):
        # ArComp has to precede the mixin in the bases to hit this
        namespace = {
            "binary": ("nonexistent",),
            "default_unpack_cmd": "{binary}",
            "exts": frozenset([".test-missing-streams"]),
        }
        with pytest.raises(ValueError, match="does not implement _streams"):
            type("Broken", (ArComp, _Archive), namespace)
        assert ".test-missing-streams" not in ArComp.known_exts

    def test_unknown_extenstion(self, tmp_path):
        file = tmp_path / "test.file"
        with pytest.raises(ArCompError, match="unknown compression file extension"):
            ArComp(file, ext=".foo")

    def test_missing_tar(self, tmp_path, tar_file):
        with hide_binary("gtar", "tar"), chdir(tmp_path):
            with pytest.raises(ArCompError, match="required binary not found"):
                ArComp(tar_file, ext=".tar").unpack(dest=tmp_path)

    def test_tar(self, tmp_path, tar_file):
        with chdir(tmp_path):
            ArComp(tar_file, ext=".tar").unpack(dest=tmp_path)
        assert (tmp_path / "file1").read_text() == "Hello world"
        assert (tmp_path / "file2").read_text() == "Larry the Cow"

    def test_tar_bz2(self, tmp_path, tar_bz2_file):
        with chdir(tmp_path):
            ArComp(tar_bz2_file, ext=".tar.bz2").unpack(dest=tmp_path)
        assert (tmp_path / "file1").read_text() == "Hello world"
        assert (tmp_path / "file2").read_text() == "Larry the Cow"

    def test_tbz2(self, tmp_path, tbz2_file):
        with chdir(tmp_path):
            ArComp(tbz2_file, ext=".tbz2").unpack(dest=tmp_path)
        assert (tmp_path / "file1").read_text() == "Hello world"
        assert (tmp_path / "file2").read_text() == "Larry the Cow"

    def test_fallback_tbz2(self, tmp_path, tbz2_file):
        with hide_binary(*next(zip(*_TarBZ2.compress_binary[:-1]))):
            with chdir(tmp_path):
                ArComp(tbz2_file, ext=".tbz2").unpack(dest=tmp_path)
            assert (tmp_path / "file1").read_text() == "Hello world"
            assert (tmp_path / "file2").read_text() == "Larry the Cow"

    def test_no_fallback_tbz2(self, tmp_path, tbz2_file):
        with hide_binary(*next(zip(*_TarBZ2.compress_binary))), chdir(tmp_path):
            with pytest.raises(ArCompError, match="no compression binary"):
                ArComp(tbz2_file, ext=".tbz2").unpack(dest=tmp_path)

    def test_tar_lzma(self, tmp_path, tar_lzma_file):
        with chdir(tmp_path):
            ArComp(tar_lzma_file, ext=".tar.lzma").unpack(dest=tmp_path)
        assert (tmp_path / "file1").read_text() == "Hello world"
        assert (tmp_path / "file2").read_text() == "Larry the Cow"

    def test_no_fallback_tar_lzma(self, tmp_path, tar_lzma_file):
        with hide_binary(*next(zip(*_TarLZMA.compress_binary))), chdir(tmp_path):
            with pytest.raises(ArCompError, match="no compression binary"):
                ArComp(tar_lzma_file, ext=".tar.lzma").unpack(dest=tmp_path)

    def test_lzma(self, tmp_path, lzma_file):
        dest = tmp_path / "file"
        with chdir(tmp_path):
            ArComp(lzma_file, ext=".lzma").unpack(dest=dest)
        assert (dest).read_bytes() == b"Hello world"

    def test_braces_in_path(self, tmp_path, tar_file):
        # the path is interpolated into the command, it must not then be
        # interpreted as a format string of its own
        path = tmp_path / "{pkg}-1.0.tar"
        shutil.copyfile(tar_file, path)
        with chdir(tmp_path):
            ArComp(str(path), ext=".tar").unpack(dest=tmp_path)
        assert (tmp_path / "file1").read_text() == "Hello world"

    def test_failure_reports_stderr(self, tmp_path):
        path = tmp_path / "corrupt.tar"
        path.write_text("this is not a tar archive")
        with chdir(tmp_path), pytest.raises(ArCompError) as excinfo:
            ArComp(str(path), ext=".tar").unpack(dest=tmp_path)
        # the message is the command's stderr, not the generic fallback
        assert "unpacking failed" not in str(excinfo.value)
        assert str(excinfo.value).strip() == str(excinfo.value)
        assert excinfo.value.code > 0

    def test_rejects_spawn_kwargs(self, tmp_path, tar_file):
        # the old spawn kwargs pass-through is gone, uid/gid are now the
        # subprocess spelled user/group
        with chdir(tmp_path), pytest.raises(TypeError):
            ArComp(tar_file, ext=".tar").unpack(dest=tmp_path, uid=os.getuid())

    def test_user_group(self, tmp_path, tar_file):
        # use the current ids so the test needs no privileges of its own
        with chdir(tmp_path):
            ArComp(tar_file, ext=".tar").unpack(
                dest=tmp_path, user=os.getuid(), group=os.getgid()
            )
        assert (tmp_path / "file1").read_text() == "Hello world"

    def test_missing_binary_leaves_no_dest(self, tmp_path, lzma_file):
        # the command is resolved before dest is opened
        dest = tmp_path / "file"
        with (
            hide_binary("lzma"),
            chdir(tmp_path),
            pytest.raises(ArCompError, match="required binary not found"),
        ):
            ArComp(lzma_file, ext=".lzma").unpack(dest=dest)
        assert not dest.exists()
