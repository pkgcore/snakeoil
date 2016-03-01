# Copyright 2015 Tim Harder <radhermit@gmail.com>
# License: BSD/GPL2

__all__ = ('mount', 'umount')

import ctypes
from ctypes.util import find_library
import os

from snakeoil.osutils import supported_systems

# mount flags synced from sys/mount.h, see the mount(2) man page for details.
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

# umount2 flags synced from sys/mount.h, see the umount2 man page for details.
MNT_FORCE = 1
MNT_DETACH = 2
MNT_EXPIRE = 4
UMOUNT_NOFOLLOW = 8


@supported_systems('linux')
def mount(source, target, fstype, flags, data=None):
    """Call mount(2); see the man page for details."""
    libc = ctypes.CDLL(find_library('c'), use_errno=True)
    source = source.encode() if isinstance(source, basestring) else source
    target = target.encode() if isinstance(target, basestring) else target
    fstype = fstype.encode() if isinstance(fstype, basestring) else fstype
    if libc.mount(source, target, fstype, ctypes.c_ulong(flags), data) != 0:
        e = ctypes.get_errno()
        raise OSError(e, os.strerror(e))


@supported_systems('linux')
def umount(target, flags=None):
    """Call umount or umount2; see the umount(2) man page for details."""
    libc = ctypes.CDLL(find_library('c'), use_errno=True)
    target = target.encode() if isinstance(target, basestring) else target
    args = []
    func = libc.umount
    if flags is not None:
        args.append(ctypes.c_ulong(flags))
        func = libc.umount2
    if func(target, *args) != 0:
        e = ctypes.get_errno()
        raise OSError(e, os.strerror(e))
