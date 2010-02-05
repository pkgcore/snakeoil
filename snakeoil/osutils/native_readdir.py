# Copyright: 2006-2007 Brian Harring <ferringb@gmail.com>
# Copyright: 2006 Marien Zwart <marienz@gentoo.org>
# License: BSD/GPL2

"""Wrapper for readdir which grabs file type from d_type."""


import os, errno
from stat import (S_IFDIR, S_IFREG, S_IFCHR, S_IFBLK, S_IFIFO, S_IFLNK, S_IFSOCK,
    S_IFMT, S_ISDIR, S_ISREG)

listdir = os.listdir

# we can still use the cpy pjoin here, just need to do something about the
# import cycle.
pjoin = os.path.join

def stat_swallow_enoent(path, check, default=False, stat=os.stat):
    try:
        return check(stat(path).st_mode)
    except OSError, oe:
        if oe.errno == errno.ENOENT:
            return default
        raise

def listdir_dirs(path, followSymlinks=True):
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
    scheck = S_ISREG
    pjf = pjoin
    if followSymlinks:
        return [x for x in os.listdir(path) if
            stat_swallow_enoent(pjf(path, x), scheck)]
    lstat = os.lstat
    return [x for x in os.listdir(path) if
        scheck(lstat(pjf(path, x)).st_mode)]

def readdir(path):
    pjf = pjoin
    assocs = {
        S_IFREG: "file",
        S_IFDIR: "directory",
        S_IFLNK: "symlink",
        S_IFCHR: "chardev",
        S_IFBLK: "block",
        S_IFSOCK: "socket",
        S_IFIFO: "fifo",
    }
    things = listdir(path)
    lstat = os.lstat
    return [(name, assocs[S_IFMT(lstat(pjf(path, name)).st_mode)]) for name in things]
