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
    'abspath', 'abssymlink', 'ensure_dirs', 'join', 'pjoin', 'listdir_files',
    'listdir_dirs', 'listdir', 'readdir', 'normpath', 'unlink_if_exists',
    'FsLock', 'GenericFailed', 'LockException', 'NonExistent',
    'supported_systems',
)

import errno
import fcntl
import os
import stat
import sys

# No name '_readdir' in module osutils
# pylint: disable=E0611

try:
    from . import _readdir as module
except ImportError:
    from . import native_readdir as module

# delay this... it's a 1ms hit, and not a lot of the consumers
# force utf8 codepaths yet.
from ..klass import steal_docs

listdir = module.listdir
listdir_dirs = module.listdir_dirs
listdir_files = module.listdir_files
readdir = module.readdir

del module


def supported_systems(*systems):
    """Decorator limiting functions to specified systems.

    Supported platforms are passed as string arguments. When run on any other
    system (determined using sys.platform), the function fails immediately with
    NotImplementedError.

    Example usage:

    >>> from snakeoil.osutils import supported_systems
    >>> @supported_systems('linux', 'darwin')
    >>> def func(param):
    ...     return True
    >>>
    >>> if sys.platform.startswith(('linux', 'darwin')):
    >>>     assert func() == True

    NotImplementedError is raised on platforms that aren't supported.
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
                raise NotImplementedError('%s not supported on %s'
                                          % (f.__name__, sys.platform))
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

    try:
        st = os.stat(path)
    except OSError:
        base = os.path.sep
        try:
            um = os.umask(0)
            # if the dir perms would lack +wx, we have to force it
            force_temp_perms = ((mode & 0o300) != 0o300)
            resets = []
            apath = normpath(os.path.abspath(path))
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
                        sticky_parent = (st.st_mode & stat.S_ISGID)

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
            if ((gid != -1 and gid != st.st_gid) or
                    (uid != -1 and uid != st.st_uid)):
                os.chown(path, uid, gid)
            if minimal:
                if mode != (st.st_mode & mode):
                    os.chmod(path, st.st_mode | mode)
            elif mode != (st.st_mode & 0o7777):
                os.chmod(path, mode)
        except OSError:
            return False
    return True


def abssymlink(path):
    """Return the absolute path of a symlink

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


def abspath(path):
    """resolve a path absolutely, including symlink resolving.

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
    """normalize path- //usr/bin becomes /usr/bin, /usr/../bin becomes /bin

    see :py:func:`os.path.normpath` for details- this function differs from
    `os.path.normpath` only in that it'll convert leading '//' into '/'
    """
    newpath = os.path.normpath(mypath)
    double_sep = b'//' if isinstance(newpath, bytes) else '//'
    if newpath.startswith(double_sep):
        return newpath[1:]
    return newpath

native_join = os.path.join

try:
    from .._posix import normpath, join
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


class FsLock:
    """fnctl based filesystem lock"""
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
        # write access is needed to acquire LOCK_EX
        # https://github.com/pkgcore/snakeoil/pull/23
        flags = os.O_RDWR
        if self.create:
            flags |= os.O_CREAT
        try:
            self.fd = os.open(self.path, flags)
        except OSError as e:
            raise GenericFailed(self.path, e) from e

    def _enact_change(self, flags, blocking):
        if self.fd is None:
            self._acquire_fd()
        # We do it this way, due to the fact try/except is a bit of a hit.
        # Note that LOCK_UN can never block, and combining it with LOCK_NB
        # triggers ValueError on Solaris.
        # https://github.com/pkgcore/snakeoil/pull/23
        if not blocking and flags != fcntl.LOCK_UN:
            try:
                fcntl.flock(self.fd, flags | fcntl.LOCK_NB)
            except IOError as e:
                if ie.errno == errno.EAGAIN:
                    return False
                raise GenericFailed(self.path, e) from e
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
    """wrap os.unlink, ignoring if the file doesn't exist

    :param path: a non directory target to ensure doesn't exist
    """
    try:
        os.unlink(path)
    except EnvironmentError as e:
        if e.errno != errno.ENOENT:
            raise


def sizeof_fmt(size, binary=True):
    if binary:
        units = ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB')
        increment = 1024.0
    else:
        units = ('B', 'kB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB')
        increment = 1000.0

    for i, x in enumerate(units):
        if size < increment or i == len(units):
            return "%3.1f %s" % (size, x)
        size /= increment


def stat_mtime_long(path, st=None):
    return (os.stat(path) if st is None else st)[stat.ST_MTIME]


def lstat_mtime_long(path, st=None):
    return (os.lstat(path) if st is None else st)[stat.ST_MTIME]


def fstat_mtime_long(fd, st=None):
    return (os.fstat(fd) if st is None else st)[stat.ST_MTIME]
