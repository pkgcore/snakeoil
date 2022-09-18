"""Version information."""

import errno
import os
import subprocess
from datetime import datetime
from importlib import import_module
from typing import NamedTuple, Optional

_ver = None


def get_version(project, repo_file, api_version=None) -> str:
    """Determine a project's version information.

    Standardized version retrieval for git-based projects. In summary, if the
    api_version isn't specified it imports __version__ from the main module for
    the project. Next it tries to import extended information from a generated
    file (for packages using snakeoil's custom sdist phase) and if that fails
    assumes it's in a git repo and grabs the git info instead.

    :param project: module name
    :param repo_file: file belonging to module
    :param api_version: version for the project, if not specified __version__
        is imported from the main project module
    :return: a string describing the project version
    """
    global _ver  # pylint: disable=global-statement
    if _ver is None:
        version_info = None
        if api_version is None:
            try:
                api_version = getattr(import_module(project), '__version__')
            except ImportError:
                raise ValueError(f'no {project} module in the syspath')
        try:
            version_info = getattr(
                import_module(f'{project}._verinfo'), 'version_info')
        except ImportError:
            # we're probably in a git repo
            path = os.path.dirname(os.path.abspath(repo_file))
            version_info = get_git_version(path)

        if version_info is None:
            suffix = ''
        elif version_info.tag == api_version:
            suffix = f' -- released {version_info.date_rfc2822}'
        else:
            rev = version_info.short_revision
            date = version_info.date_rfc2822
            commits = f'-{version_info.commits}' if version_info.commits is not None else ''
            suffix = f'{commits}-g{rev} -- {date}'

        _ver = f'{project} {api_version}{suffix}'
    return _ver


def _run_git(path: str, *cmd: str):
    env = dict(os.environ)
    for key in env.copy(): # pragma: no cover
        if key.startswith("LC_"):
            del env[key]
    env["LC_CTYPE"] = "C"
    env["LC_ALL"] = "C"
    r = subprocess.Popen(('git', ) + cmd, env=env, cwd=path,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    stdout, _ = r.communicate()
    return stdout, r.returncode


class GitVersion(NamedTuple):
    revision: str
    date: datetime
    tag: Optional[str] = None
    commits: Optional[int] = None

    @property
    def date_rfc2822(self):
        return self.date.strftime('%a, %d %b %Y %H:%M:%S %z')

    @property
    def short_revision(self):
        return self.revision[:7]


def get_git_version(path: str) -> Optional[GitVersion]:
    """Return git related revision data."""
    path = os.path.abspath(path)
    try:
        stdout, ret = _run_git(path, "log", "--format=%H\n%aI", "HEAD^..HEAD")
        if ret != 0:
            return None

        revision, date = stdout.decode().splitlines()
        tag = _get_git_tag(path, revision)

        # get number of commits since most recent tag
        stdout, ret = _run_git(path, 'describe', '--tags', '--abbrev=0')
        commits = None
        if ret == 0:
            prev_tag = stdout.decode().strip()
            stdout, ret = _run_git(
                path, 'log', '--oneline', f'{prev_tag}..HEAD')
            if ret == 0:
                commits = len(stdout.decode().splitlines())

        return GitVersion(
            revision=revision, date=datetime.fromisoformat(date),
            tag=tag, commits=commits,
        )
    except EnvironmentError as exc:
        # ENOENT is thrown when the git binary can't be found.
        if exc.errno != errno.ENOENT:
            raise
        return None


def _get_git_tag(path, rev):
    stdout, _ = _run_git(path, 'name-rev', '--tag', rev)
    tag = stdout.decode().split()
    if len(tag) != 2:
        return None
    tag = tag[1]
    if not tag.startswith("tags/"):
        return None
    tag = tag[len("tags/"):]
    if tag.endswith("^0"):
        tag = tag[:-2]
    if tag.startswith("v"):
        tag = tag[1:]
    return tag
