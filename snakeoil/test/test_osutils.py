# -*- coding: utf-8 -*-
# Copyright: 2005-2011 Brian Harring <ferringb@gmail.com>
# Copyright: 2006 Marien Zwart <marienz@gentoo.org>
# License: BSD/GPL2

import errno
import fcntl
import grp
import os
import stat
import sys
import tempfile
import unittest

try:
    from unittest import mock
except ImportError:
    import mock

from snakeoil import osutils, compatibility
from snakeoil.fileutils import touch
from snakeoil.test import TestCase, SkipTest, mk_cpy_loadable_testcase
from snakeoil.osutils import native_readdir, supported_systems
from snakeoil.osutils.mount import mount, umount, MNT_FORCE, MS_BIND
from snakeoil.test.mixins import TempDirMixin

pjoin = os.path.join


class ReaddirCommon(TempDirMixin):

    module = native_readdir

    def setUp(self):
        TempDirMixin.setUp(self)
        self.subdir = pjoin(self.dir, 'dir')
        os.mkdir(self.subdir)
        touch(pjoin(self.dir, 'file'))
        os.mkfifo(pjoin(self.dir, 'fifo'))

    def _test_missing(self, funcs):
        for func in funcs:
            self.assertRaises(OSError, func, pjoin(self.dir, 'spork'))


class NativeListDirTest(ReaddirCommon):

    def test_listdir(self):
        self.assertEqual(['dir', 'fifo', 'file'],
                         sorted(self.module.listdir(self.dir)))
        self.assertEqual([], self.module.listdir(self.subdir))

    def test_listdir_dirs(self):
        self.assertEqual(['dir'], self.module.listdir_dirs(self.dir))
        self.assertEqual([], self.module.listdir_dirs(self.subdir))

    def test_listdir_files(self):
        self.assertEqual(['file'], self.module.listdir_files(self.dir))
        self.assertEqual([], self.module.listdir_dirs(self.subdir))

    def test_missing(self):
        return self._test_missing((
            self.module.listdir,
            self.module.listdir_dirs,
            self.module.listdir_files,
        ))

    def test_dangling_sym(self):
        os.symlink("foon", pjoin(self.dir, "monkeys"))
        self.assertEqual(["file"], self.module.listdir_files(self.dir))


class NativeReaddirTest(ReaddirCommon):
    # TODO: test char/block devices and sockets, devices might be a bit hard
    # because it seems like you need to be root to create them in linux
    def test_readdir(self):
        os.symlink("foon", pjoin(self.dir, "monkeys"))
        os.symlink(pjoin(self.dir, "file"), pjoin(self.dir, "sym"))
        self.assertEqual(set([
            ("dir", "directory"),
            ("file", "file"),
            ("fifo", "fifo"),
            ("monkeys", "symlink"),
            ("sym", "symlink"),
        ]), set(self.module.readdir(self.dir)))
        self.assertEqual([], self.module.readdir(self.subdir))

    def test_missing(self):
        return self._test_missing((self.module.readdir,))


try:
    # No name "readdir" in module osutils
    # pylint: disable=E0611
    from snakeoil.osutils import _readdir
except ImportError:
    _readdir = None


class CPyListDirTest(NativeListDirTest):
    module = _readdir
    if _readdir is None:
        skip = "cpython extension isn't available"


class CPyReaddirTest(NativeReaddirTest):
    module = _readdir
    if _readdir is None:
        skip = "cpython extension isn't available"


class EnsureDirsTest(TempDirMixin):

    def check_dir(self, path, uid, gid, mode):
        self.assertTrue(os.path.isdir(path))
        st = os.stat(path)
        self.assertEqual(stat.S_IMODE(st.st_mode), mode,
                         '0%o != 0%o' % (stat.S_IMODE(st.st_mode), mode))
        self.assertEqual(st.st_uid, uid)
        self.assertEqual(st.st_gid, gid)

    def test_ensure_dirs(self):
        # default settings
        path = pjoin(self.dir, 'foo', 'bar')
        self.assertTrue(osutils.ensure_dirs(path))
        self.check_dir(path, os.geteuid(), os.getegid(), 0o777)

    def test_minimal_nonmodifying(self):
        path = pjoin(self.dir, 'foo', 'bar')
        self.assertTrue(osutils.ensure_dirs(path, mode=0o755))
        os.chmod(path, 0o777)
        self.assertTrue(osutils.ensure_dirs(path, mode=0o755, minimal=True))
        self.check_dir(path, os.geteuid(), os.getegid(), 0o777)

    def test_minimal_modifying(self):
        path = pjoin(self.dir, 'foo', 'bar')
        self.assertTrue(osutils.ensure_dirs(path, mode=0o750))
        self.assertTrue(osutils.ensure_dirs(path, mode=0o005, minimal=True))
        self.check_dir(path, os.geteuid(), os.getegid(), 0o755)

    def test_create_unwritable_subdir(self):
        path = pjoin(self.dir, 'restricted', 'restricted')
        # create the subdirs without 020 first
        self.assertTrue(osutils.ensure_dirs(os.path.dirname(path)))
        self.assertTrue(osutils.ensure_dirs(path, mode=0o020))
        self.check_dir(path, os.geteuid(), os.getegid(), 0o020)
        # unrestrict it
        osutils.ensure_dirs(path)
        self.check_dir(path, os.geteuid(), os.getegid(), 0o777)

    def test_path_is_a_file(self):
        # fail if passed a path to an existing file
        path = pjoin(self.dir, 'file')
        touch(path)
        self.assertTrue(os.path.isfile(path))
        self.assertFalse(osutils.ensure_dirs(path, mode=0o700))

    def test_non_dir_in_path(self):
        # fail if one of the parts of the path isn't a dir
        path = pjoin(self.dir, 'file', 'dir')
        touch(pjoin(self.dir, 'file'))
        self.assertFalse(osutils.ensure_dirs(path, mode=0o700))

    def test_mkdir_failing(self):
        # fail if os.mkdir fails
        with mock.patch('snakeoil.osutils.os.mkdir') as mkdir:
            mkdir.side_effect = OSError(30, 'Read-only file system')
            path = pjoin(self.dir, 'dir')
            self.assertFalse(osutils.ensure_dirs(path, mode=0o700))

            # force temp perms
            self.assertFalse(osutils.ensure_dirs(path, mode=0o400))
            mkdir.side_effect = OSError(17, 'File exists')
            self.assertFalse(osutils.ensure_dirs(path, mode=0o700))

    def test_chmod_or_chown_failing(self):
        # fail if chmod or chown fails
        path = pjoin(self.dir, 'dir')
        os.mkdir(path)
        os.chmod(path, 0o750)

        with mock.patch('snakeoil.osutils.os.chmod') as chmod, \
                mock.patch('snakeoil.osutils.os.chown') as chown:
            chmod.side_effect = OSError(5, 'Input/output error')

            # chmod failure when file exists and trying to reset perms to match
            # the specified mode
            self.assertFalse(osutils.ensure_dirs(path, mode=0o005, minimal=True))
            self.assertFalse(osutils.ensure_dirs(path, mode=0o005, minimal=False))
            os.rmdir(path)

            # chmod failure when resetting perms on parents
            self.assertFalse(osutils.ensure_dirs(path, mode=0o400))
            os.rmdir(path)

            # chown failure when resetting perms on parents
            chmod.side_effect = None
            chown.side_effect = OSError(5, 'Input/output error')
            self.assertFalse(osutils.ensure_dirs(path, uid=1000, gid=1000, mode=0o400))

    def test_reset_sticky_parent_perms(self):
        # make sure perms are reset after traversing over sticky parents
        sticky_parent = pjoin(self.dir, 'dir')
        path = pjoin(sticky_parent, 'dir')
        os.mkdir(sticky_parent)
        os.chmod(sticky_parent, 0o2755)
        pre_sticky_parent = os.stat(sticky_parent)
        self.assertTrue(osutils.ensure_dirs(path, mode=0o700))
        post_sticky_parent = os.stat(sticky_parent)
        self.assertEqual(pre_sticky_parent.st_mode, post_sticky_parent.st_mode)

    def test_mode(self):
        path = pjoin(self.dir, 'mode', 'mode')
        self.assertTrue(osutils.ensure_dirs(path, mode=0o700))
        self.check_dir(path, os.geteuid(), os.getegid(), 0o700)
        # unrestrict it
        osutils.ensure_dirs(path)
        self.check_dir(path, os.geteuid(), os.getegid(), 0o777)

    def test_gid(self):
        # abuse the portage group as secondary group
        try:
            portage_gid = grp.getgrnam('portage').gr_gid
        except KeyError:
            raise SkipTest('the portage group does not exist')
        if portage_gid not in os.getgroups():
            raise SkipTest('you are not in the portage group')
        path = pjoin(self.dir, 'group', 'group')
        self.assertTrue(osutils.ensure_dirs(path, gid=portage_gid))
        self.check_dir(path, os.geteuid(), portage_gid, 0o777)
        self.assertTrue(osutils.ensure_dirs(path))
        self.check_dir(path, os.geteuid(), portage_gid, 0o777)
        self.assertTrue(osutils.ensure_dirs(path, gid=os.getegid()))
        self.check_dir(path, os.geteuid(), os.getegid(), 0o777)


class SymlinkTest(TempDirMixin):

    def test_abssymlink(self):
        target = pjoin(self.dir, 'target')
        linkname = pjoin(self.dir, 'link')
        os.mkdir(target)
        os.symlink('target', linkname)
        self.assertEqual(osutils.abssymlink(linkname), target)


class Native_NormPathTest(TestCase):

    func = staticmethod(osutils.native_normpath)

    def test_normpath(self):
        f = self.func

        def check(src, val):
            got = f(src)
            self.assertEqual(got, val, msg=(
                "%r: expected %r, got %r" % (src, val, got)))

        check('/foo/', '/foo')
        check('//foo/', '/foo')
        check('//foo/.', '/foo')
        check('//..', '/')
        check('//..//foo', '/foo')
        check('/foo/..', '/')
        check('..//foo', '../foo')
        check('../foo/../', '..')
        check('../', '..')
        check('../foo/..', '..')
        check('../foo/../dar', '../dar')
        check('.//foo', 'foo')
        check('/foo/../../', '/')
        check('/foo/../../..', '/')
        check('/tmp/foo/../dar/', '/tmp/dar')
        check('/tmp/foo/../dar', '/tmp/dar')

        if compatibility.is_py3k:
            check(u'/tmṕ/föo//../dár', u'/tmṕ/dár')
            check(b'/tm\xe1\xb9\x95/f\xc3\xb6o//../d\xc3\xa1r', b'/tm\xe1\xb9\x95/d\xc3\xa1r')
            check(u'/föó/..', u'/')
            check(b'/f\xc3\xb6\xc3\xb3/..', b'/')


@unittest.skipIf(osutils.normpath is osutils.native_normpath, "extension isn't compiled")
class Cpy_NormPathTest(Native_NormPathTest):

    func = staticmethod(osutils.normpath)


@unittest.skipIf(osutils.join is osutils.native_join, "extension isn't compiled")
class Cpy_JoinTest(unittest.TestCase):

    def assertSame(self, val):
        self.assertEqual(
            osutils.native_join(*val),
            osutils.join(*val),
            msg="for %r, expected %r, got %r" % (
                val,
                osutils.native_join(*val),
                osutils.join(*val)))

    def test_reimplementation(self):
        vals = [
            [""],
            ["foo"],
            ["", "foo"],
            ["foo", "dar"],
            ["foo", "/bar"],
            ["/bar", "dar"],
            ["/bar", "../dar"],
            ["", "../dar"]
        ]

        if compatibility.is_py3k:
            vals.extend([
                [u"/bár", u"dãr"],
                [b"/b\xc3\xa1r", b"d\xc3\xa3r"],
            ])

        for x in vals:
            self.assertSame(x)

    # proper type checking was done in py3.5
    @unittest.skipUnless(sys.hexversion >= 0x03050000, 'requires >=py3.5')
    def test_reimplementation_errors(self):
        # various type errors
        errors = [
            [],
            [1],
            ["foo", 1],
            ["foo", "/bar", []],
        ]

        for x in errors:
            with self.assertRaises(TypeError):
                osutils.native_join(*x)
            with self.assertRaises(TypeError):
                osutils.join(*x)


# TODO: more error condition testing
class FsLockTest(TempDirMixin):

    def test_nonexistent(self):
        self.assertRaises(osutils.NonExistent, osutils.FsLock,
                          pjoin(self.dir, 'missing'))

    def test_fslock_read_lock(self):
        path = pjoin(self.dir, 'lockfile-read')
        lock = osutils.FsLock(path, True)
        # do this all non-blocking to avoid hanging tests
        self.assertTrue(lock.acquire_read_lock(False))
        # file should exist now
        with open(path, 'r+') as f:
            # acquire and release a read lock
            fcntl.flock(f, fcntl.LOCK_SH | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN)
            # we can't acquire an exclusive lock
            self.assertRaises(
                IOError, fcntl.flock, f, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_fslock_release_read_lock(self):
        path = pjoin(self.dir, 'lockfile-release-read')
        lock = osutils.FsLock(path, True)
        # do this all non-blocking to avoid hanging tests
        self.assertTrue(lock.acquire_read_lock(False))
        lock.release_read_lock()
        # file should exist now
        with open(path, 'r+') as f:
            # but now we can
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN)

    def test_fslock_write_lock(self):
        path = pjoin(self.dir, 'lockfile-write')
        lock = osutils.FsLock(path, True)
        # do this all non-blocking to avoid hanging tests
        # acquire an exclusive/write lock
        self.assertTrue(lock.acquire_write_lock(False))
        # file should exist now
        with open(path, 'r+') as f:
            self.assertRaises(
                IOError, fcntl.flock, f, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_fslock_release_write_lock(self):
        path = pjoin(self.dir, 'lockfile-release-write')
        lock = osutils.FsLock(path, True)
        # do this all non-blocking to avoid hanging tests
        # acquire an exclusive/write lock
        self.assertTrue(lock.acquire_write_lock(False))
        lock.release_write_lock()
        # file should exist now
        with open(path, 'r+') as f:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN)

    def test_fslock_downgrade_lock(self):
        path = pjoin(self.dir, 'lockfile-downgrade')
        lock = osutils.FsLock(path, True)
        # do this all non-blocking to avoid hanging tests
        # acquire an exclusive/write lock
        self.assertTrue(lock.acquire_write_lock(False))
        # downgrade to read lock
        self.assertTrue(lock.acquire_read_lock())
        # file should exist now
        with open(path, 'r+') as f:
            fcntl.flock(f, fcntl.LOCK_SH | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN)
            self.assertRaises(
                IOError, fcntl.flock, f, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_fslock_release_downgraded_lock(self):
        path = pjoin(self.dir, 'lockfile-release-downgraded')
        lock = osutils.FsLock(path, True)
        # do this all non-blocking to avoid hanging tests
        # acquire an exclusive/write lock
        self.assertTrue(lock.acquire_write_lock(False))
        # downgrade to read lock
        self.assertTrue(lock.acquire_read_lock())
        # and release
        lock.release_read_lock()
        # file should exist now
        with open(path, 'r+') as f:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN)


class TestAccess(TempDirMixin):

    if os.getuid() != 0:
        skip = "these tests must be ran as root"

    func = staticmethod(osutils.fallback_access)

    def test_fallback(self):
        fp = pjoin(self.dir, "file")
        # create the file
        touch(fp)
        os.chmod(fp, 000)
        self.assertFalse(self.func(fp, os.X_OK))
        self.assertTrue(self.func(fp, os.W_OK))
        self.assertTrue(self.func(fp, os.R_OK))
        self.assertTrue(self.func(fp, os.W_OK | os.R_OK))
        self.assertFalse(self.func(fp, os.W_OK | os.R_OK | os.X_OK))


class Test_unlink_if_exists(TempDirMixin):

    func = staticmethod(osutils.unlink_if_exists)

    def test_it(self):
        f = self.func
        path = pjoin(self.dir, 'target')
        f(path)
        self.write_file(path, 'w', '')
        f(path)
        self.assertFalse(os.path.exists(path))
        # and once more for good measure...
        f(path)


class SupportedSystems(unittest.TestCase):

    def test_supported_system(self):
        @supported_systems('supported')
        def func():
            return True

        with mock.patch('snakeoil.osutils.sys') as _sys:
            _sys.configure_mock(platform='supported')
            self.assertTrue(func())

    def test_unsupported_system(self):
        @supported_systems('unsupported')
        def func():
            return True

        with self.assertRaises(NotImplementedError):
            func()

        # make sure we're iterating through the system params correctly
        with mock.patch('snakeoil.osutils.sys') as _sys:
            _sys.configure_mock(platform='u')
            with self.assertRaises(NotImplementedError):
                func()

    def test_multiple_systems(self):
        @supported_systems('darwin', 'linux')
        def func():
            return True

        with mock.patch('snakeoil.osutils.sys') as _sys:
            _sys.configure_mock(platform='nonexistent')
            with self.assertRaises(NotImplementedError):
                func()

            for platform in ('linux2', 'darwin'):
                _sys.configure_mock(platform=platform)
                self.assertTrue(func())


class Mount(unittest.TestCase):

    def setUp(self):
        self.source = tempfile.mkdtemp()
        self.target = tempfile.mkdtemp()

    def tearDown(self):
        os.rmdir(self.source)
        os.rmdir(self.target)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'supported on Linux only')
    def test_args_bytes(self):
        # The initial source, target, and fstype arguments to mount(2) must be
        # byte strings; if they are unicode strings the arguments get mangled
        # leading to errors when the syscall is run. This confirms mount() from
        # snakeoil.osutils always converts the arguments into byte strings.
        for source, target, fstype in ((b'source', b'target', b'fstype'),
                                       (u'source', u'target', u'fstype')):
            with mock.patch('snakeoil.osutils.mount.ctypes') as mock_ctypes:
                with self.assertRaises(OSError):
                    mount(source, target, fstype, MS_BIND)
                mount_call = next(x for x in mock_ctypes.mock_calls if x[0] == 'CDLL().mount')
                for arg in mount_call[1][0:3]:
                    self.assertIsInstance(arg, bytes)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'supported on Linux only')
    def test_missing_dirs(self):
        with self.assertRaises(OSError) as cm:
            mount('source', 'target', None, MS_BIND)
        self.assertEqual(cm.exception.errno, errno.ENOENT)

    @unittest.skipIf(os.getuid() == 0, 'this test must be run as non-root')
    @unittest.skipUnless(sys.platform.startswith('linux'), 'supported on Linux only')
    def test_no_perms(self):
        with self.assertRaises(OSError) as cm:
            mount(self.source, self.target, None, MS_BIND)
        self.assertTrue(cm.exception.errno in (errno.EPERM, errno.EACCES))
        with self.assertRaises(OSError) as cm:
            umount(self.target)
        self.assertTrue(cm.exception.errno in (errno.EPERM, errno.EINVAL))

    @unittest.skipIf(os.getuid() != 0, 'this test must be run as root')
    @unittest.skipUnless(sys.platform.startswith('linux'), 'supported on Linux only')
    def test_root(self):
        # test umount
        mount(self.source, self.target, None, MS_BIND)
        umount(self.target)
        # test umount2
        mount(self.source, self.target, None, MS_BIND)
        umount(self.target, MNT_FORCE)


cpy_readdir_loaded_Test = mk_cpy_loadable_testcase(
    "snakeoil.osutils._readdir", "snakeoil.osutils", "listdir", "listdir")
cpy_posix_loaded_Test = mk_cpy_loadable_testcase(
    "snakeoil._posix", "snakeoil.osutils", "normpath", "normpath")
