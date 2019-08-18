"""Wrapper for readdir which grabs file type from d_type."""


import errno
import os
from stat import (S_IFDIR, S_IFREG, S_IFCHR, S_IFBLK, S_IFIFO, S_IFLNK, S_IFSOCK,
                  S_IFMT, S_ISDIR, S_ISREG)

from ..mappings import ProtectedDict

listdir = os.listdir

# we can still use the cpy pjoin here, just need to do something about the
# import cycle.
pjoin = os.path.join

def stat_swallow_enoent(path, check, default=False, stat=os.stat):
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
    pjf = pjoin
    lstat = os.lstat
    if followSymlinks:
        return [x for x in os.listdir(path) if
                stat_swallow_enoent(pjf(path, x), scheck)]
    lstat = os.lstat
    return [x for x in os.listdir(path) if
            scheck(lstat(pjf(path, x)).st_mode)]

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
    pjf = pjoin
    if followSymlinks:
        return [x for x in os.listdir(path) if
                stat_swallow_enoent(pjf(path, x), scheck)]
    lstat = os.lstat
    return [x for x in os.listdir(path) if
            scheck(lstat(pjf(path, x)).st_mode)]

# we store this outside the function to ensure that
# the strings used are reused, thus avoiding unneeded
# allocations
d_type_mapping = ProtectedDict({
    S_IFREG: "file",
    S_IFDIR: "directory",
    S_IFLNK: "symlink",
    S_IFCHR: "chardev",
    S_IFBLK: "block",
    S_IFSOCK: "socket",
    S_IFIFO: "fifo",
})

def readdir(path):
    """
    Given a directory, return a list of (filename, filetype)

    see :py:data:`d_type_mappings` for the translation used

    :param path: path of a directory to scan
    :return: list of (filename, filetype)
    """
    pjf = pjoin
    things = listdir(path)
    lstat = os.lstat
    dt = d_type_mapping
    return [(name, dt[S_IFMT(lstat(pjf(path, name)).st_mode)]) for name in things]
