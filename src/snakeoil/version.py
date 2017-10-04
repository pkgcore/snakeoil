# Copyright: 2011 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""Version information."""

import errno
from importlib import import_module
import os

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
                raise ValueError('no %s module in the syspath' % (project,))
        try:
            version_info = getattr(import_module(
                '%s._verinfo' % (project,)), 'version_info')
        except ImportError:
            # we're probably in a git repo
            cwd = os.path.dirname(os.path.abspath(repo_file))
            version_info = get_git_version(cwd)

        if version_info is None:
            s = ", extended version info unavailable"
        elif version_info['tag'] == api_version:
            s = ', released %s' % (version_info['date'],)
        else:
            s = ('-g%s, %s' % (version_info['rev'][:7], version_info['date']))

        _ver = '%s %s%s' % (project, api_version, s)
    return _ver


def _run_git(cwd, cmd):
    import subprocess

    env = dict(os.environ)
    env["LC_CTYPE"] = "C"

    with open(os.devnull, 'wb') as null:
        r = subprocess.Popen(
            ['git'] + list(cmd), stdout=subprocess.PIPE, env=env,
            stderr=null, cwd=cwd)

    stdout = r.communicate()[0]
    return stdout, r.returncode


def get_git_version(cwd):
    """:return: git sha1 rev"""

    cwd = os.path.abspath(cwd)
    try:
        stdout, ret = _run_git(cwd, ["log", "--format=%H\n%ad", "HEAD^..HEAD"])

        if ret != 0:
            return None

        data = stdout.decode("ascii").splitlines()

        return {
            "rev": data[0],
            "date": data[1],
            'tag': _get_git_tag(cwd, data[0]),
        }
    except EnvironmentError as e:
        # ENOENT is thrown when the git binary can't be found.
        if e.errno != errno.ENOENT:
            raise
        return None


def _get_git_tag(cwd, rev):
    stdout, _ = _run_git(cwd, ['name-rev', '--tag', rev])
    tag = stdout.decode("ascii").split()
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
