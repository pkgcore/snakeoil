import errno
import os
import re
from datetime import datetime

from ..version import get_git_version

def module_version(repodir, moduledir):
    """Determine a module's version.

    Based on the assumption that a module defines __version__.
    """
    version = None
    try:
        with open(os.path.join(moduledir, '__init__.py'), encoding='utf-8') as f:
            version = re.search(
                r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
                f.read(), re.MULTILINE).group(1)
    except IOError as exc:
        if exc.errno == errno.ENOENT:
            pass
        else:
            raise

    if version is None:
        raise RuntimeError(f'Cannot find version for module in: {moduledir}')

    # use versioning scheme similar to setuptools_scm for untagged versions
    git_version = get_git_version(str(repodir))
    if git_version:
        tag = git_version['tag']
        if tag is None:
            commits = git_version['commits']
            rev = git_version['rev'][:7]
            date = datetime.strptime(git_version['date'], '%a, %d %b %Y %H:%M:%S %z')
            date = datetime.strftime(date, '%Y%m%d')
            if commits is not None:
                version += f'.dev{commits}'
            version += f'+g{rev}.d{date}'
        elif tag != version:
            raise RuntimeError(
                f'unmatched git tag {tag!r} and module version {version!r}')

    return version
