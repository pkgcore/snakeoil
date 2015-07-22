# Copyright: 2011 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""Version information."""

from importlib import import_module
import os

_ver = None


def get_version(project, file_in_the_repo):
    """:return: a string describing the project version."""
    global _ver  # pylint: disable=global-statement
    if _ver is None:
        version_info = None
        api_version = getattr(import_module(project), '__version__')
        try:
            version_info = getattr(import_module(
                '%s._verinfo' % (project,)), 'version_info')
        except AttributeError:
            # we're probably in a git repo
            try:
                from pkgdist import get_git_version
                cwd = os.path.dirname(os.path.abspath(file_in_the_repo))
                version_info = get_git_version(cwd)
            except ImportError:
                pass

        if version_info is None:
            s = "extended version info unavailable"
        elif version_info['tag'] == api_version:
            s = 'released %s' % (version_info['date'],)
        else:
            s = ('vcs version %s, date %s' %
                 (version_info['rev'], version_info['date']))

        _ver = '%s %s\n%s' % (project, api_version, s)
    return _ver
