"""Version information."""

import errno
from importlib import import_module
import os
import subprocess

_ver = None


def get_version(project, repo_file, api_version=None):
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
            s = " -- extended version info unavailable"
        elif version_info['tag'] == api_version:
            s = f" -- released {version_info['date']}"
        else:
            rev = version_info['rev'][:7]
            date = version_info['date']
            commits = version_info.get('commits', None)
            commits = f'-{commits}' if commits is not None else ''
            s = f'{commits}-g{rev} -- {date}'

        _ver = f'{project} {api_version}{s}'
    return _ver


def _run_git(path, cmd):
    env = dict(os.environ)
    env["LC_CTYPE"] = "C"

    r = subprocess.Popen(
        ['git'] + list(cmd), stdout=subprocess.PIPE, env=env,
        stderr=subprocess.DEVNULL, cwd=path)

    stdout = r.communicate()[0]
    return stdout, r.returncode


def get_git_version(path):
    """Return git related revision data."""
    path = os.path.abspath(path)
    try:
        stdout, ret = _run_git(path, ["log", "--format=%H\n%aD", "HEAD^..HEAD"])

        if ret != 0:
            return None

        data = stdout.decode().splitlines()
        tag = _get_git_tag(path, data[0])

        # get number of commits since most recent tag
        stdout, ret = _run_git(path, ['describe', '--tags', '--abbrev=0'])
        prev_tag = None
        commits = None
        if ret == 0:
            prev_tag = stdout.decode().strip()
            stdout, ret = _run_git(
                path, ['log', '--oneline', f'{prev_tag}..HEAD'])
            if ret == 0:
                commits = len(stdout.decode().splitlines())

        return {
            'rev': data[0],
            'date': data[1],
            'tag': tag,
            'commits': commits,
        }
    except EnvironmentError as e:
        # ENOENT is thrown when the git binary can't be found.
        if e.errno != errno.ENOENT:
            raise
        return None


def _get_git_tag(path, rev):
    stdout, _ = _run_git(path, ['name-rev', '--tag', rev])
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
