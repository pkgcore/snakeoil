# Copyright: 2005-2011 Brian Harring <ferringb@gmail.com>
# Copyright: 2006 Marien Zwart <marienz@gentoo.org>
# License: BSD/GPL2

import errno
import fcntl
import grp
import os
import stat
import tempfile
import unittest

try:
    from unittest import mock
except ImportError:
    import mock

from snakeoil import osutils
from snakeoil.test import TestCase, SkipTest, mk_cpy_loadable_testcase
from snakeoil.osutils import native_readdir
from snakeoil.test.mixins import TempDirMixin

pjoin = os.path.join


class ReaddirCommon(TempDirMixin):

    module = native_readdir

    def setUp(self):
        TempDirMixin.setUp(self)
        self.subdir = pjoin(self.dir, 'dir')
        os.mkdir(self.subdir)
        open(pjoin(self.dir, 'file'), 'w').close()
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
        self.check_dir(path, os.geteuid(), os.getegid(), 0777)

    def test_minimal_nonmodifying(self):
        path = pjoin(self.dir, 'foo', 'bar')
        self.assertTrue(osutils.ensure_dirs(path, mode=0755))
        os.chmod(path, 0777)
        self.assertTrue(osutils.ensure_dirs(path, mode=0755, minimal=True))
        self.check_dir(path, os.geteuid(), os.getegid(), 0777)

    def test_minimal_modifying(self):
        path = pjoin(self.dir, 'foo', 'bar')
        self.assertTrue(osutils.ensure_dirs(path, mode=0750))
        self.assertTrue(osutils.ensure_dirs(path, mode=0005, minimal=True))
        self.check_dir(path, os.geteuid(), os.getegid(), 0755)

    def test_create_unwritable_subdir(self):
        path = pjoin(self.dir, 'restricted', 'restricted')
        # create the subdirs without 020 first
        self.assertTrue(osutils.ensure_dirs(os.path.dirname(path)))
        self.assertTrue(osutils.ensure_dirs(path, mode=0020))
        self.check_dir(path, os.geteuid(), os.getegid(), 0020)
        # unrestrict it
        osutils.ensure_dirs(path)
        self.check_dir(path, os.geteuid(), os.getegid(), 0777)

    def test_mode(self):
        path = pjoin(self.dir, 'mode', 'mode')
        self.assertTrue(osutils.ensure_dirs(path, mode=0700))
        self.check_dir(path, os.geteuid(), os.getegid(), 0700)
        # unrestrict it
        osutils.ensure_dirs(path)
        self.check_dir(path, os.geteuid(), os.getegid(), 0777)

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
        self.check_dir(path, os.geteuid(), portage_gid, 0777)
        self.assertTrue(osutils.ensure_dirs(path))
        self.check_dir(path, os.geteuid(), portage_gid, 0777)
        self.assertTrue(osutils.ensure_dirs(path, gid=os.getegid()))
        self.check_dir(path, os.geteuid(), os.getegid(), 0777)


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


class Cpy_NormPathTest(Native_NormPathTest):

    func = staticmethod(osutils.normpath)
    if osutils.normpath is osutils.native_normpath:
        skip = "extension isn't compiled"


class Cpy_JoinTest(TestCase):

    if osutils.join is osutils.native_join:
        skip = "etension isn't compiled"

    def assertSame(self, val):
        self.assertEqual(
            osutils.native_join(*val),
            osutils.join(*val),
            msg="for %r, expected %r, got %r" % (
                val,
                osutils.native_join(*val),
                osutils.join(*val)))

    def test_reimplementation(self):
        for vals in [
                ["", "foo"],
                ["foo", "dar"],
                ["foo", "/bar"],
                ["/bar", "dar"],
                ["/bar", "../dar"],
                ["", "../dar"]
            ]:
            self.assertSame(vals)



# TODO: more error condition testing
class FsLockTest(TempDirMixin):

    def test_nonexistent(self):
        self.assertRaises(osutils.NonExistent, osutils.FsLock,
                          pjoin(self.dir, 'missing'))

    def test_locking(self):
        path = pjoin(self.dir, 'lockfile')
        lock = osutils.FsLock(path, True)
        # do this all non-blocking to avoid hanging tests
        self.assertTrue(lock.acquire_read_lock(False))
        # file should exist now
        with open(path) as f:
            # acquire and release a read lock
            fcntl.flock(f, fcntl.LOCK_SH | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN | fcntl.LOCK_NB)
            # we can't acquire an exclusive lock
            self.assertRaises(
                IOError, fcntl.flock, f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock.release_read_lock()
            # but now we can
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertFalse(lock.acquire_read_lock(False))
            self.assertFalse(lock.acquire_write_lock(False))
            fcntl.flock(f, fcntl.LOCK_UN | fcntl.LOCK_NB)
            # acquire an exclusive/write lock
            self.assertTrue(lock.acquire_write_lock(False))
            self.assertRaises(
                IOError, fcntl.flock, f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # downgrade to read lock
            self.assertTrue(lock.acquire_read_lock())
            fcntl.flock(f, fcntl.LOCK_SH | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN | fcntl.LOCK_NB)
            self.assertRaises(
                IOError, fcntl.flock, f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # and release
            lock.release_read_lock()
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN | fcntl.LOCK_NB)

            self.assertTrue(lock.acquire_write_lock(False))
            lock.release_write_lock()
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN | fcntl.LOCK_NB)


class TestAccess(TempDirMixin):

    if osutils.access is os.access:
        skip = "os.access is usable, no need to test"
    elif os.getuid() != 0:
        skip = "these tests must be ran as root"

    func = staticmethod(osutils.access)

    def test_fallback(self):
        fp = pjoin(self.dir, "file")
        os.chmod(fp, 000)
        self.assertFalse(self.func(fp, os.X_OK))
        self.assertTrue(self.func(fp, os.W_OK))
        self.assertTrue(self.func(fp, os.R_OK))
        self.assertTrue(self.func(fp, os.W_OK|os.R_OK))
        self.assertFalse(self.func(fp, os.W_OK|os.R_OK|os.X_OK))


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


class Mount(unittest.TestCase):

    def setUp(self):
        self.source = tempfile.mkdtemp()
        self.target = tempfile.mkdtemp()

    def tearDown(self):
        os.rmdir(self.source)
        os.rmdir(self.target)

    def test_args_bytes(self):
        # The initial source, target, and fstype arguments to mount(2) must be
        # byte strings; if they are unicode strings the arguments get mangled
        # leading to errors when the syscall is run. This confirms mount() from
        # snakeoil.osutils always converts the arguments into byte strings.
        with mock.patch('snakeoil.osutils.ctypes') as mock_ctypes:
            with self.assertRaises(OSError):
                osutils.mount('source', 'target', 'fstype', osutils.MS_BIND)
            mount_call = next(x for x in mock_ctypes.mock_calls if x[0] == 'CDLL().mount')
            for arg in mount_call[1][0:3]:
                self.assertIsInstance(arg, bytes)

    def test_missing_dirs(self):
        with self.assertRaises(OSError) as cm:
            osutils.mount('source', 'target', 'none', osutils.MS_BIND)
        self.assertEqual(cm.exception.errno, errno.ENOENT)

    @unittest.skipIf(os.getuid() == 0, 'this test must be run as non-root')
    def test_no_perms(self):
        with self.assertRaises(OSError) as cm:
            osutils.mount(self.source, self.target, 'none', osutils.MS_BIND)
        self.assertEqual(cm.exception.errno, errno.EPERM)


cpy_readdir_loaded_Test = mk_cpy_loadable_testcase(
    "snakeoil.osutils._readdir", "snakeoil.osutils", "listdir", "listdir")
cpy_posix_loaded_Test = mk_cpy_loadable_testcase(
    "snakeoil._posix", "snakeoil.osutils", "normpath", "normpath")
