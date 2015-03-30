# Copyright 2004-2011 Brian Harring <ferringb@gmail.com>
# Copyright 2006 Marien Zwart <marienz@gentoo.org>
# License: BSD/GPL2

"""
OS related functionality

This module is primarily optimized implementations of various filesystem operations,
written for posix specifically.  If this is a non-posix system (or extensions were
disabled) it falls back to native python implementations that yield no real speed gains.

A rough example of the performance benefits, collected from a core2 2.4GHz running
python 2.6.5, w/ an EXT4 FS on a 160GB x25-M for the FS related invocations (it's worth
noting the IO is pretty fast in this setup- for slow IO like nfs, the speedup for extension
vs native for listdir* functionality is a fair bit larger).

Rough stats:

========================================================  =========   ===============
python -m timeit code snippet                             native      extension time
========================================================  =========   ===============
join("/usr/portage", "dev-util", "bsdiff", "ChangeLog")   2.8 usec    0.36 usec
normpath("/usr/portage/foon/blah/dar")                    5.52 usec   0.15 usec
normpath("/usr/portage//foon/blah//dar")                  5.66 usec   0.15 usec
normpath("/usr/portage/./foon/../blah/")                  5.92 usec   0.15 usec
listdir_files("/usr/lib64") # 2338 entries, 990 syms      18.6 msec   4.17 msec
listdir_files("/usr/lib64", False) # same dir content     16.9 msec   1.48 msec
readfile("/etc/passwd") # 1899 bytes                      20.4 usec   4.05 usec
readfile("tmp-file") # 1MB                                300 usec    259 usec
list(readlines("/etc/passwd")) # 1899 bytes, 34 lines     37.3 usec   12.8 usec
list(readlines("/etc/passwd", False)) # leave whitespace  26.7 usec   12.8 usec
========================================================  =========   ===============

If you're just invoking join or normpath, or reading a file or two a couple of times,
these optimizations are probably overkill.  If you're doing lots of path manipulation,
reading files, scanning directories, etc, these optimizations start adding up
pretty quickly.
"""

__all__ = (
    'abspath', 'abssymlink', 'ensure_dirs', 'join', 'pjoin',
    'listdir_files', 'listdir_dirs', 'listdir',
    'readdir', 'normpath', 'unlink_if_exists',
    'FsLock', 'GenericFailed',
    'LockException', 'NonExistent', 'mount',
)

import errno
import fcntl
import os
import stat

# No name '_readdir' in module osutils
# pylint: disable=E0611

try:
    from snakeoil.osutils import _readdir as module
except ImportError:
    from snakeoil.osutils import native_readdir as module

# delay this... it's a 1ms hit, and not a lot of the consumers
# force utf8 codepaths yet.
from snakeoil import compatibility
from snakeoil.demandload import demandload
from snakeoil.klass import steal_docs
from snakeoil.weakrefs import WeakRefFinalizer

demandload('ctypes')

listdir = module.listdir
listdir_dirs = module.listdir_dirs
listdir_files = module.listdir_files
readdir = module.readdir

del module

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

def ensure_dirs(path, gid=-1, uid=-1, mode=0777, minimal=True):
    """
    ensure dirs exist, creating as needed with (optional) gid, uid, and mode.

    be forewarned- if mode is specified to a mode that blocks the euid
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

    try:
        st = os.stat(path)
    except OSError:
        base = os.path.sep
        try:
            um = os.umask(0)
            # if the dir perms would lack +wx, we have to force it
            force_temp_perms = ((mode & 0300) != 0300)
            resets = []
            apath = normpath(os.path.abspath(path))
            sticky_parent = False

            for directory in apath.split(os.path.sep):
                base = join(base, directory)
                try:
                    st = os.stat(base)
                    if not stat.S_ISDIR(st.st_mode):
                        return False

                    # if it's a subdir, we need +wx at least
                    if apath != base:
                        if (st.st_mode & 0300) != 0300:
                            try:
                                os.chmod(base, (st.st_mode | 0300))
                            except OSError:
                                return False
                            resets.append((base, st.st_mode))
                        sticky_parent = (st.st_gid & stat.S_ISGID)

                except OSError:
                    # nothing exists.
                    try:
                        if force_temp_perms:
                            if not _safe_mkdir(base, 0700):
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
                if uid != -1 or gid != -1:
                    os.chown(base, uid, gid)
            except OSError:
                return False

        finally:
            os.umask(um)
        return True
    else:
        try:
            if ((gid != -1 and gid != st.st_gid) or
                    (uid != -1 and uid != st.st_uid)):
                os.chown(path, uid, gid)
            if minimal:
                if mode != (st.st_mode & mode):
                    os.chmod(path, st.st_mode | mode)
            elif mode != (st.st_mode & 07777):
                os.chmod(path, mode)
        except OSError:
            return False
    return True


def abssymlink(path):
    """
    Return the absolute path of a symlink

    :param path: filepath to resolve
    :return: resolved path
    :raise: EnvironmentError, errno=ENINVAL if the requested path isn't
        a symlink
    """
    mylink = os.readlink(path)
    if mylink[0] != '/':
        mydir = os.path.dirname(path)
        mylink = mydir + '/' + mylink
    return normpath(mylink)


def abspath(path):
    """
    resolve a path absolutely, including symlink resolving.

    Note that if it's a symlink and the target doesn't exist, it'll still
    return the target.

    :param path: filepath to resolve.
    :raise: EnvironmentError some errno other than an ENOENT or EINVAL
        is encountered
    :return: the absolute path calculated against the filesystem
    """
    path = os.path.abspath(path)
    try:
        return abssymlink(path)
    except EnvironmentError as e:
        if e.errno not in (errno.ENOENT, errno.EINVAL):
            raise
        return path


def native_normpath(mypath):
    """
    normalize path- //usr/bin becomes /usr/bin, /usr/../bin becomes /bin

    see :py:func:`os.path.normpath` for details- this function differs from
    `os.path.normpath` only in that it'll convert leading '//' into '/'
    """
    newpath = os.path.normpath(mypath)
    if newpath.startswith('//'):
        return newpath[1:]
    return newpath

native_join = os.path.join

try:
    from snakeoil._posix import normpath, join
except ImportError:
    normpath = native_normpath
    join = native_join


# convenience.  importing join into a namespace is ugly, pjoin less so
pjoin = join

class LockException(Exception):
    """Base lock exception class"""
    def __init__(self, path, reason):
        Exception.__init__(self, path, reason)
        self.path, self.reason = path, reason

class NonExistent(LockException):
    """Missing file/dir exception"""

    def __init__(self, path, reason=None):
        LockException.__init__(self, path, reason)

    def __str__(self):
        return (
            "Lock action for '%s' failed due to not being a valid dir/file %s"
            % (self.path, self.reason))

class GenericFailed(LockException):
    """The fallback lock exception class.

    Covers perms, IOError's, and general whackyness.
    """
    def __str__(self):
        return "Lock action for '%s' failed due to '%s'" % (
            self.path, self.reason)


# should the fd be left open indefinitely?
# IMO, it shouldn't, but opening/closing everytime around is expensive


class FsLock(object):

    """
    fnctl based filesystem lock
    """

    __metaclass__ = WeakRefFinalizer
    __slots__ = ("path", "fd", "create")

    def __init__(self, path, create=False):
        """
        :param path: fs path for the lock
        :param create: controls whether the file will be created
            if the file doesn't exist.
            If true, the base dir must exist, and it will create a file.
            If you want to lock via a dir, you have to ensure it exists
            (create doesn't suffice).
        :raise NonExistent: if no file/dir exists for that path,
            and cannot be created
        """
        self.path = path
        self.fd = None
        self.create = create
        if not create:
            if not os.path.exists(path):
                raise NonExistent(path)

    def _acquire_fd(self):
        flags = os.R_OK
        if self.create:
            flags |= os.O_CREAT
        try:
            self.fd = os.open(self.path, flags)
        except OSError as oe:
            compatibility.raise_from(GenericFailed(self.path, oe))

    def _enact_change(self, flags, blocking):
        if self.fd is None:
            self._acquire_fd()
        # we do it this way, due to the fact try/except is a bit of a hit
        if not blocking:
            try:
                fcntl.flock(self.fd, flags|fcntl.LOCK_NB)
            except IOError as ie:
                if ie.errno == errno.EAGAIN:
                    return False
                compatibility.raise_from(GenericFailed(self.path, ie))
        else:
            fcntl.flock(self.fd, flags)
        return True

    def acquire_write_lock(self, blocking=True):
        """
        Acquire an exclusive lock

        Note if you have a read lock, it implicitly upgrades atomically

        :param blocking: if enabled, don't return until we have the lock
        :return: True if lock is acquired, False if not.
        """
        return self._enact_change(fcntl.LOCK_EX, blocking)

    def acquire_read_lock(self, blocking=True):
        """
        Acquire a shared lock

        Note if you have a write lock, it implicitly downgrades atomically

        :param blocking: if enabled, don't return until we have the lock
        :return: True if lock is acquired, False if not.
        """
        return self._enact_change(fcntl.LOCK_SH, blocking)

    def release_write_lock(self):
        """Release an write/exclusive lock if held"""
        self._enact_change(fcntl.LOCK_UN, False)

    def release_read_lock(self):
        """Release an shared/read lock if held"""
        self._enact_change(fcntl.LOCK_UN, False)

    def __del__(self):
        # alright, it's 5:45am, yes this is weird code.
        try:
            if self.fd is not None:
                self.release_read_lock()
        finally:
            if self.fd is not None:
                os.close(self.fd)


@steal_docs(os.access)
def fallback_access(path, mode, root=0):
    try:
        st = os.lstat(path)
    except EnvironmentError:
        return False
    if mode == os.F_OK:
        return True
    # rules roughly are as follows; if process uid == file uid, those perms
    # apply.
    # if groups match... that perm group is the fallback (authorative)
    # if neither, then other
    # if root, w/r is guranteed, x is actually checked
    # note posix says X_OK can be True, which is a worthless result, hence this
    # fallback for systems that take advantage of that posix misfeature.

    myuid = os.getuid()

    # if we're root... pull out X_OK and check that alone.  the rules of
    # X_OK under linux (which this function emulates) are that any +x is a True
    # as for WR, that's always allowed (well not always- selinux may change that)

    if myuid == 0:
        mode &= os.X_OK
        if not mode:
            # w/r are always True for root, so return up front
            return True
        # py3k doesn't like octal syntax; this is 0111
        return bool(st.st_mode & 73)

    mygroups = os.getgroups()

    if myuid == st.st_uid:
        # shift to the user octet, filter to 3 bits, verify intersect.
        return mode == (mode & ((st.st_mode >> 6) & 0x7))
    if st.st_gid in mygroups:
        return mode == (mode & ((st.st_mode >> 3) & 0x7))
    return mode == (mode & (st.st_mode & 0x7))

if os.uname()[0].lower() == 'sunos':
    access = fallback_access
    access.__name__ = 'access'
else:
    access = os.access

def unlink_if_exists(path):
    """
    wrap os.unlink, ignoring if the file doesn't exist

    :param path: a non directory target to ensure doesn't exist
    """
    try:
        os.unlink(path)
    except EnvironmentError as e:
        if e.errno != errno.ENOENT:
            raise


def stat_mtime_long(path, st=None):
    return (os.stat(path) if st is None else st)[stat.ST_MTIME]

def lstat_mtime_long(path, st=None):
    return (os.lstat(path) if st is None else st)[stat.ST_MTIME]

def fstat_mtime_long(fd, st=None):
    return (os.fstat(fd) if st is None else st)[stat.ST_MTIME]


# Flags synced from sys/mount.h, see mount(2) for details.
MS_RDONLY = 1
MS_NOSUID = 2
MS_NODEV = 4
MS_NOEXEC = 8
MS_SYNCHRONOUS = 16
MS_REMOUNT = 32
MS_MANDLOCK = 64
MS_DIRSYNC = 128
MS_NOATIME = 1024
MS_NODIRATIME = 2048
MS_BIND = 4096
MS_MOVE = 8192
MS_REC = 16384
MS_SILENT = 32768
MS_POSIXACL = 1 << 16
MS_UNBINDABLE = 1 << 17
MS_PRIVATE = 1 << 18
MS_SLAVE = 1 << 19
MS_SHARED = 1 << 20
MS_RELATIME = 1 << 21
MS_KERNMOUNT = 1 << 22
MS_I_VERSION = 1 << 23
MS_STRICTATIME = 1 << 24
MS_ACTIVE = 1 << 30
MS_NOUSER = 1 << 31


def mount(source, target, fstype, flags, data=None):
    """Call mount(2); see the man page for details."""
    libc = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)
    if compatibility.is_py3k:
        source = source.encode() if isinstance(source, str) else source
        target = target.encode() if isinstance(target, str) else target
        fstype = fstype.encode() if isinstance(fstype, str) else fstype
    if libc.mount(source, target, fstype, ctypes.c_ulong(flags), data) != 0:
        e = ctypes.get_errno()
        raise OSError(e, os.strerror(e))
