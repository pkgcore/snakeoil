"""
OS related functionality
"""

__all__ = (
    "abspath",
    "ensure_dirs",
    "join",
    "pjoin",
    "listdir_files",
    "listdir_dirs",
    "listdir",
    "normpath",
    "unlink_if_exists",
    "supported_systems",
)

import errno
import os
import stat
import sys
from stat import (
    S_ISDIR,
    S_ISREG,
)

from snakeoil._internals import deprecated

listdir = deprecated(
    "Use os.listdir",
    removal_in=(0, 12, 0),
    qualname="snakeoil.osutils.listdir",
)(lambda *a, **kw: os.listdir(*a, **kw))


def supported_systems(*systems):
    """Decorator limiting functions to specified systems.

    Supported platforms are passed as string arguments. When run on any other
    system (determined using sys.platform), the function fails immediately with
    ``NotImplementedError``.

    Example usage:

    >>> from snakeoil.osutils import supported_systems
    >>> @supported_systems('linux', 'darwin')
    >>> def func(param):
    ...     return True
    >>>
    >>> if sys.platform.startswith(('linux', 'darwin')):
    >>>     assert func() == True

    ``NotImplementedError`` is raised on platforms that aren't supported.

    >>> @supported_systems('nonexistent')
    >>> def func2(param):
    ...     return False
    >>>
    >>> func2()
    Traceback (most recent call last):
        ...
    NotImplementedError: func2 not supported on nonexistent
    """

    def _decorator(f):
        def _wrapper(*args, **kwargs):
            if sys.platform.startswith(systems):
                return f(*args, **kwargs)
            else:
                raise NotImplementedError(
                    "%s not supported on %s" % (f.__name__, sys.platform)
                )

        return _wrapper

    return _decorator


def _safe_mkdir(path, mode):
    try:
        os.mkdir(path, mode)
    except OSError as e:
        # if it exists already and is a dir, non issue.
        if e.errno != errno.EEXIST:
            return False
        if not stat.S_ISDIR(os.stat(path).st_mode):
            return False
    return True


def ensure_dirs(path, gid=-1, uid=-1, mode=0o777, minimal=True):
    """ensure dirs exist, creating as needed with (optional) gid, uid, and mode.

    Be forewarned- if mode is specified to a mode that blocks the euid
    from accessing the dir, this code *will* try to create the dir.

    :param path: directory to ensure exists on disk
    :param gid: a valid GID to set any created directories to
    :param uid: a valid UID to set any created directories to
    :param mode: permissions to set any created directories to
    :param minimal: boolean controlling whether or not the specified mode
        must be enforced, or is the minimal permissions necessary.  For example,
        if mode=0755, minimal=True, and a directory exists with mode 0707,
        this will restore the missing group perms resulting in 757.
    :return: True if the directory could be created/ensured to have those
        permissions, False if not.
    """

    join = os.path.join
    try:
        st = os.stat(path)
    except OSError:
        base = os.path.sep
        try:
            um = os.umask(0)
            # if the dir perms would lack +wx, we have to force it
            force_temp_perms = (mode & 0o300) != 0o300
            resets = []
            apath = os.path.normpath(os.path.abspath(path))
            sticky_parent = False

            for directory in apath.split(os.path.sep):
                base = join(base, directory)
                try:
                    st = os.stat(base)
                    if not stat.S_ISDIR(st.st_mode):
                        # one of the path components isn't a dir
                        return False

                    # if it's a subdir, we need +wx at least
                    if apath != base:
                        sticky_parent = st.st_mode & stat.S_ISGID

                except OSError:
                    # nothing exists.
                    try:
                        if force_temp_perms:
                            if not _safe_mkdir(base, 0o700):
                                return False
                            resets.append((base, mode))
                        else:
                            if not _safe_mkdir(base, mode):
                                return False
                            if base == apath and sticky_parent:
                                resets.append((base, mode))
                            if gid != -1 or uid != -1:
                                os.chown(base, uid, gid)
                    except OSError:
                        return False

            try:
                for base, m in reversed(resets):
                    os.chmod(base, m)
                    if gid != -1 or uid != -1:
                        os.chown(base, uid, gid)
            except OSError:
                return False

        finally:
            os.umask(um)
        return True
    else:
        if not os.path.isdir(path):
            # don't change perms for existing paths that aren't dirs
            return False

        try:
            if (gid != -1 and gid != st.st_gid) or (uid != -1 and uid != st.st_uid):
                os.chown(path, uid, gid)
            if minimal:
                if mode != (st.st_mode & mode):
                    os.chmod(path, st.st_mode | mode)
            elif mode != (st.st_mode & 0o7777):
                os.chmod(path, mode)
        except OSError:
            return False
    return True


def _abssymlink(path):
    """Return the absolute path of a symlink

    :param path: filepath to resolve
    :return: resolved path
    :raises EnvironmentError: with errno=ENINVAL if the requested path isn't
        a symlink
    """
    mylink = os.readlink(path)
    if mylink[0] != "/":
        mydir = os.path.dirname(path)
        mylink = mydir + "/" + mylink
    return os.path.normpath(mylink)


def force_symlink(target, link):
    """Force a symlink to be created.

    :param target: target to link to
    :param link: link to create
    """
    try:
        os.symlink(target, link)
    except OSError as e:
        if e.errno == errno.EEXIST:
            os.remove(link)
            os.symlink(target, link)
        else:
            raise


@deprecated("Use os.path.abspath", removal_in=(0, 12, 0))
def abspath(path):
    """resolve a path absolutely, including symlink resolving.

    Note that if it's a symlink and the target doesn't exist, it'll still
    return the target.

    :param path: filepath to resolve.
    :raises EnvironmentError: some errno other than an ENOENT or EINVAL
        is encountered
    :return: the absolute path calculated against the filesystem
    """
    path = os.path.abspath(path)
    try:
        return _abssymlink(path)
    except EnvironmentError as e:
        if e.errno not in (errno.ENOENT, errno.EINVAL):
            raise
        return path


@deprecated(
    "Use os.path.normpath or pathlib.  Be aware that os.path doesn't strip prefix // into /",
    removal_in=(0, 12, 0),
)
def normpath(mypath: str) -> str:
    """normalize path- //usr/bin becomes /usr/bin, /usr/../bin becomes /bin

    see :py:func:`os.path.normpath` for details- this function differs from
    `os.path.normpath` only in that it'll convert leading '//' into '/'
    """
    newpath = os.path.normpath(mypath)
    double_sep = b"//" if isinstance(newpath, bytes) else "//"
    if newpath.startswith(double_sep):
        return newpath[1:]
    return newpath


# convenience.  importing join into a namespace is ugly, pjoin less so
pjoin = deprecated(
    "Use os.path.join",
    removal_in=(0, 12, 0),
    qualname="snakeoil.osutils.pjoin",
)(lambda *a, **kw: os.path.join(*a, **kw))
join = deprecated(
    "Use os.path.join",
    removal_in=(0, 12, 0),
    qualname="snakeoil.osutils.join",
)(lambda *a, **kw: os.path.join(*a, **kw))


def unlink_if_exists(path):
    """wrap os.unlink, ignoring if the file doesn't exist

    :param path: a non directory target to ensure doesn't exist
    """
    try:
        os.unlink(path)
    except EnvironmentError as e:
        if e.errno != errno.ENOENT:
            raise


def sizeof_fmt(size, binary=True):
    prefixes = ("k", "M", "G", "T", "P", "E", "Z", "Y")
    increment = 1024.0 if binary else 1000.0

    prefix = ""
    for x in prefixes:
        if size < increment:
            break
        size /= increment
        prefix = x
    if binary and prefix:
        prefix = f"{prefix.upper()}i"
    return f"{size:3.1f} {prefix}B"


def stat_mtime_long(path, st=None):
    return (os.stat(path) if st is None else st)[stat.ST_MTIME]


def lstat_mtime_long(path, st=None):
    return (os.lstat(path) if st is None else st)[stat.ST_MTIME]


def fstat_mtime_long(fd, st=None):
    return (os.fstat(fd) if st is None else st)[stat.ST_MTIME]


def _stat_swallow_enoent(path, check, default=False, stat=os.stat):
    try:
        return check(stat(path).st_mode)
    except OSError as oe:
        if oe.errno == errno.ENOENT:
            return default
        raise


def listdir_dirs(path, followSymlinks=True):
    """
    Return a list of all subdirectories within a directory

    :param path: directory to scan
    :param followSymlinks: this controls if symlinks are resolved.
        If True and the symlink resolves to a directory, it is returned,
        else if False it isn't returned.
    :return: list of directories within `path`
    """
    scheck = S_ISDIR
    lstat = os.lstat
    if followSymlinks:
        return [
            x
            for x in os.listdir(path)
            if _stat_swallow_enoent(os.path.join(path, x), scheck)
        ]
    lstat = os.lstat
    return [x for x in os.listdir(path) if scheck(lstat(os.path.join(path, x)).st_mode)]


def listdir_files(path, followSymlinks=True):
    """
    Return a list of all files within a directory

    :param path: directory to scan
    :param followSymlinks: this controls if symlinks are resolved.
        If True and the symlink resolves to a file, it is returned,
        else if False it isn't returned.
    :return: list of files within `path`
    """

    scheck = S_ISREG
    if followSymlinks:
        return [
            x
            for x in os.listdir(path)
            if _stat_swallow_enoent(os.path.join(path, x), scheck)
        ]
    lstat = os.lstat
    return [x for x in os.listdir(path) if scheck(lstat(os.path.join(path, x)).st_mode)]
