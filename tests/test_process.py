import os
from pathlib import Path
import tempfile

import pytest
from snakeoil import process


class TestFindBinary:

    script = "findpath-test.sh"

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        orig_path = os.environ["PATH"]
        os.environ["PATH"] = ":".join([str(tmp_path)] + orig_path.split(":"))

        yield

        os.environ["PATH"] = orig_path

    def test_found(self, tmp_path):
        fp = tmp_path / self.script
        fp.touch()
        fp.chmod(0o750)
        assert str(fp) == process.find_binary(self.script)

    def test_missing(self):
        with pytest.raises(process.CommandNotFound):
            process.find_binary(self.script)

    def test_fallback(self):
        fallback = process.find_binary(self.script, fallback=os.path.join('bin', self.script))
        assert fallback == os.path.join('bin', self.script)

    def test_not_executable(self, tmp_path):
        fp = tmp_path / self.script
        fp.touch()
        fp.chmod(0o640)
        with pytest.raises(process.CommandNotFound):
            process.find_binary(self.script)
        with pytest.raises(process.CommandNotFound):
            process.find_binary(fp)

    def test_path_override(self, tmp_path):
        # check PATH override
        tempdir = Path(tempfile.mkdtemp(dir=tmp_path))
        fp = tempdir / self.script
        fp.touch()
        fp.chmod(0o750)
        with pytest.raises(process.CommandNotFound):
            process.find_binary(self.script)
        assert str(fp) == process.find_binary(self.script, paths=[tempdir])

    def test_no_dirs(self, tmp_path):
        # make sure dirs aren't returned as binaries
        with pytest.raises(process.CommandNotFound):
            process.find_binary(tmp_path.name, str(tmp_path.parent))
        with pytest.raises(process.CommandNotFound):
            process.find_binary(tmp_path)
