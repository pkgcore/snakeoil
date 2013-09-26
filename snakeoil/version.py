# Copyright: 2011 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2


"""Version information (tied to git)."""


__version__ = '0.5.3'

_ver = None
import os

def _run(cwd, cmd):
    import subprocess

    env = dict(os.environ)
    env["LC_CTYPE"] = "C"

    null = open("/dev/null", 'wb')
    try:
        r = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=env,
            stderr=null, cwd=cwd)
    finally:
        null.close()

    stdout = r.communicate()[0]
    return stdout, r.returncode


def get_git_version(cwd):
    """:return: git sha1 rev"""

    cwd = os.path.abspath(cwd)
    stdout, ret = _run(cwd, ["git", "log", "HEAD^..HEAD"])

    if ret != 0:
        return {}

    data = stdout.decode("ascii").splitlines()
    commit = [x.split()[-1]
              for x in data if x.startswith("commit")][0]

    date = [x.split(":", 1)[-1].lstrip()
            for x in data if x.lower().startswith("date")][0]

    return {"rev":commit, "date":date, 'tag':_get_git_tag(cwd, commit)}


def _get_git_tag(cwd, rev):
    stdout, ret = _run(cwd, ['git', 'name-rev', '--tag', rev])
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


def format_version(project, file_in_the_repo, api_version):
    from snakeoil import modules
    cwd = os.path.dirname(os.path.abspath(file_in_the_repo))
    try:
        version_info = modules.load_attribute(
            '%s._verinfo.version_info' % (project,))
    except modules.FailedImport:
        version_info = get_git_version(cwd)

    if not version_info:
        s = "extend version info unavailable"
    elif version_info['tag'] == api_version:
        s = 'released %s' % (version_info['date'],)
    else:
        s = ('vcs version %s, date %s' %
            (version_info['rev'], version_info['date']))

    return '%s %s\n%s' % (project, api_version, s)


def get_version():
    """:return: a string describing the snakeoil version."""
    global _ver
    if _ver is None:
        _ver = format_version('snakeoil', __file__, __version__)
    return _ver
