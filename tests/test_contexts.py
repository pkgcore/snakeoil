import os
import subprocess
import sys
from contextlib import chdir

import pytest

from snakeoil import process
from snakeoil._internals import deprecated
from snakeoil.contexts import GitStash, syspath

GIT_BINARY = process.find_binary("git", fallback="")


@deprecated.suppress_deprecations()
def test_chdir(tmpdir):
    orig_cwd = os.getcwd()

    with chdir(str(tmpdir)):
        assert orig_cwd != os.getcwd()

    assert orig_cwd == os.getcwd()


@deprecated.suppress_deprecations()
def test_syspath(tmpdir):
    orig_syspath = tuple(sys.path)

    # by default the path gets inserted as the first element
    with syspath(tmpdir):
        assert orig_syspath != tuple(sys.path)
        assert tmpdir == sys.path[0]

    assert orig_syspath == tuple(sys.path)

    # insert path in a different position
    with syspath(tmpdir, position=1):
        assert orig_syspath != tuple(sys.path)
        assert tmpdir != sys.path[0]
        assert tmpdir == sys.path[1]

    # conditional insert and nested context managers
    with syspath(tmpdir, condition=(tmpdir not in sys.path)):
        mangled_syspath = tuple(sys.path)
        assert orig_syspath != mangled_syspath
        assert tmpdir == sys.path[0]
        # dir isn't added again due to condition
        with syspath(tmpdir, condition=(tmpdir not in sys.path)):
            assert mangled_syspath == tuple(sys.path)


@pytest.mark.skipif(not GIT_BINARY, reason="missing git binary")
class TestGitStash:
    @pytest.fixture
    def repo(self, tmp_path):
        """Initialize a git repo holding a single committed file."""

        def git(*args):
            subprocess.run(
                ("git", *args), cwd=tmp_path, check=True, capture_output=True
            )

        git("init", "-q")
        git("config", "user.email", "larry@gentoo.org")
        git("config", "user.name", "Larry The Cow")
        (tmp_path / "file").write_text("committed\n")
        git("add", "file")
        git("commit", "-qm", "initial")
        return tmp_path

    def test_nonexistent_repo(self, tmp_path):
        git_stash = GitStash(str(tmp_path))
        with pytest.raises(ValueError, match="not a git repo"):
            _ = git_stash.pending

    def test_clean_tree(self, repo):
        assert not GitStash(str(repo)).pending
        assert not GitStash(str(repo), staged=True).pending

    def test_modified_file(self, repo):
        (repo / "file").write_text("modified\n")
        assert GitStash(str(repo)).pending
        assert GitStash(str(repo), staged=True).pending

    def test_untracked_file(self, repo):
        (repo / "untracked").write_text("new\n")
        assert GitStash(str(repo)).pending
        assert GitStash(str(repo), staged=True).pending

    def test_staged_only(self, repo):
        (repo / "file").write_text("staged\n")
        subprocess.run(
            ("git", "add", "file"), cwd=repo, check=True, capture_output=True
        )
        # a fully staged change is stashed normally, but kept in staged mode
        assert GitStash(str(repo)).pending
        assert not GitStash(str(repo), staged=True).pending

    def test_roundtrip(self, repo):
        (repo / "file").write_text("modified\n")
        with GitStash(str(repo)):
            assert (repo / "file").read_text() == "committed\n"
        assert (repo / "file").read_text() == "modified\n"

    def test_roundtrip_clean_tree(self, repo):
        with GitStash(str(repo)):
            assert (repo / "file").read_text() == "committed\n"
        assert (repo / "file").read_text() == "committed\n"
