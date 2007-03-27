# Copyright: 2006-2007 Brian Harring <ferringb@gmail.com>
# Copyright: 2006 Marien Zwart <marienz@gentoo.org>
# License: GPL2

"""Wrapper for readdir which grabs file type from d_type."""


import os, errno
from stat import S_ISDIR, S_ISREG
from stat import S_IFDIR, S_IFREG, S_IFCHR, S_IFBLK, S_IFIFO, S_IFLNK, S_IFSOCK, S_IFMT

listdir = os.listdir
pjoin = os.path.join
lstat = os.lstat

def stat_swallow_enoent(path, check, default=False, stat=os.stat):
    try:
        return check(stat(path).st_mode)
    except OSError, oe:
        if oe.errno == errno.ENOENT:
            return default
        raise

def listdir_dirs(path, followSymlinks=True):
    scheck = S_ISDIR
    if followSymlinks:
        return [x for x in os.listdir(path) if
            stat_swallow_enoent(pjoin(path, x), scheck)]
    return [x for x in os.listdir(path) if
        scheck(lstat(pjoin(path, x)).st_mode)]

def listdir_files(path, followSymlinks=True):
    scheck = S_ISREG
    if followSymlinks:
        return [x for x in os.listdir(path) if
            stat_swallow_enoent(pjoin(path, x), scheck)]
    return [x for x in os.listdir(path) if
        scheck(lstat(pjoin(path, x)).st_mode)]

def readdir(path):
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
    return [(name, assocs[S_IFMT(lstat(pjoin(path, name)).st_mode)]) for name in things]

# vim: set sw=4 softtabstop=4 expandtab:
