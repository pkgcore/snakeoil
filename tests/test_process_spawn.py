import os
import signal

import pytest
from snakeoil import process
from snakeoil.contexts import chdir
from snakeoil.process import spawn

BASH_BINARY = process.find_binary("bash", fallback='')

@pytest.mark.skipif(not BASH_BINARY, reason='missing bash binary')
class TestSpawn:

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        orig_path = os.environ["PATH"]
        os.environ["PATH"] = ":".join([str(tmp_path)] + orig_path.split(":"))

        yield

        os.environ["PATH"] = orig_path

    @pytest.fixture
    def dev_null(self):
        """Return an open write file descriptor to `/dev/null`."""
        with open("/dev/null", "w") as null_file:
            yield null_file.fileno()

    def generate_script(self, tmp_path, filename, text):
        assert not os.path.isabs(filename)
        fp = tmp_path / filename
        fp.write_text("#!/usr/bin/env bash\n" + text)
        fp.chmod(0o750)
        assert fp.stat().st_mode & 0o750 == 0o750
        return fp

    def test_get_output(self, tmp_path, dev_null):
        filename = "spawn-getoutput.sh"
        for r, s, text, args in (
                [0, ["dar\n"], "echo dar\n", {}],
                [0, ["dar"], "echo -n dar", {}],
                [1, ["blah\n", "dar\n"], "echo blah\necho dar\nexit 1", {}],
                [0, [], "echo dar 1>&2", {"fd_pipes": {1: 1, 2: dev_null}}]):
            fp = self.generate_script(tmp_path, filename, text)
            assert (r, s) == spawn.spawn_get_output(str(fp), spawn_type=spawn.spawn_bash, **args)
        os.unlink(fp)

    @pytest.mark.skipif(not spawn.is_sandbox_capable(), reason="missing sandbox binary")
    def test_sandbox(self, tmp_path):
        fp = self.generate_script(
            tmp_path, "spawn-sandbox.sh", "echo $LD_PRELOAD")
        ret = spawn.spawn_get_output(str(fp), spawn_type=spawn.spawn_sandbox)
        assert ret[1], "no output; exit code was %s; script location %s" % (ret[0], fp)
        assert "libsandbox.so" in [os.path.basename(x.strip()) for x in ret[1][0].split()]
        os.unlink(fp)

    @pytest.mark.skipif(not spawn.is_sandbox_capable(), reason="missing sandbox binary")
    def test_sandbox_empty_dir(self, tmp_path):
        """sandbox gets pissy if it's ran from a nonexistent dir

        this verifies our fix works.
        """
        fp = self.generate_script(
            tmp_path, "spawn-sandbox.sh", "echo $LD_PRELOAD")
        dpath = tmp_path / "dar"
        dpath.mkdir()
        with chdir(dpath):
            dpath.rmdir()
            assert "libsandbox.so" in \
                [os.path.basename(x.strip()) for x in spawn.spawn_get_output(
                    str(fp), spawn_type=spawn.spawn_sandbox, cwd='/')[1][0].split()]
            fp.unlink()

    def test_process_exit_code(self):
        assert spawn.process_exit_code(0) == 0
        assert spawn.process_exit_code(16 << 8) == 16

    def generate_background_pid(self):
        try:
            return spawn.spawn(["sleep", "5s"], returnpid=True)[0]
        except process.CommandNotFound:
            pytest.skip("can't complete the test, sleep binary doesn't exist")

    def test_spawn_returnpid(self):
        pid = self.generate_background_pid()
        try:
            assert os.kill(pid, 0) is None, "returned pid was invalid, or sleep died"
            assert pid in spawn.spawned_pids, "pid wasn't recorded in global pids"
        finally:
            os.kill(pid, signal.SIGKILL)

    def test_cleanup_pids(self):
        pid = self.generate_background_pid()
        spawn.cleanup_pids([pid])
        with pytest.raises(OSError):
            os.kill(pid, 0)
        assert pid not in spawn.spawned_pids, "pid wasn't removed from global pids"

    def test_spawn_bash(self, capfd):
        # bash builtin for true without exec'ing true (eg, no path lookup)
        assert 0 == spawn.spawn_bash('echo bash')
        out, _err = capfd.readouterr()
        assert out.strip() == 'bash'

    def test_umask(self, tmp_path):
        fp = self.generate_script(
            tmp_path, "spawn-umask.sh", f"#!{BASH_BINARY}\numask")
        try:
            old_umask = os.umask(0)
            if old_umask == 0:
                # crap.
                desired = 0o22
                os.umask(desired)
            else:
                desired = 0
            assert str(desired).lstrip("0") == \
                spawn.spawn_get_output(str(fp))[1][0].strip().lstrip("0")
        finally:
            os.umask(old_umask)
