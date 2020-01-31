# -*- coding: utf-8 -*-

import errno
import fcntl
import grp
import os
import shutil
import stat
import sys
from unittest import mock

import pytest

from snakeoil import osutils
from snakeoil.contexts import Namespace
from snakeoil.fileutils import touch, write_file
from snakeoil.test import mk_cpy_loadable_testcase
from snakeoil.osutils import native_readdir, supported_systems
from snakeoil.osutils.mount import mount, umount, MS_BIND, MNT_DETACH
from snakeoil.test.fixtures import TempDir

pjoin = os.path.join


class ReaddirCommon(TempDir):

    module = native_readdir

    def setup(self):
        self.subdir = pjoin(self.dir, 'dir')
        os.mkdir(self.subdir)
        touch(pjoin(self.dir, 'file'))
        os.mkfifo(pjoin(self.dir, 'fifo'))

    def _test_missing(self, funcs):
        for func in funcs:
            pytest.raises(OSError, func, pjoin(self.dir, 'spork'))


class TestNativeListDir(ReaddirCommon):

    def test_listdir(self):
        assert sorted(self.module.listdir(self.dir)) == ['dir', 'fifo', 'file']
        assert self.module.listdir(self.subdir) == []

    def test_listdir_dirs(self):
        assert self.module.listdir_dirs(self.dir) == ['dir']
        assert self.module.listdir_dirs(self.subdir) == []

    def test_listdir_files(self):
        assert self.module.listdir_files(self.dir) == ['file']
        assert self.module.listdir_dirs(self.subdir) == []

    def test_missing(self):
        return self._test_missing((
            self.module.listdir,
            self.module.listdir_dirs,
            self.module.listdir_files,
        ))

    def test_dangling_sym(self):
        os.symlink("foon", pjoin(self.dir, "monkeys"))
        assert self.module.listdir_files(self.dir) == ['file']


class TestNativeReaddir(ReaddirCommon):
    # TODO: test char/block devices and sockets, devices might be a bit hard
    # because it seems like you need to be root to create them in linux

    def test_readdir(self):
        os.symlink("foon", pjoin(self.dir, "monkeys"))
        os.symlink(pjoin(self.dir, "file"), pjoin(self.dir, "sym"))
        expected = set([
            ("dir", "directory"),
            ("file", "file"),
            ("fifo", "fifo"),
            ("monkeys", "symlink"),
            ("sym", "symlink"),
        ])
        assert set(self.module.readdir(self.dir)) == expected
        assert self.module.readdir(self.subdir) == []

    def test_missing(self):
        return self._test_missing((self.module.readdir,))


try:
    # No name "readdir" in module osutils
    # pylint: disable=E0611
    from snakeoil.osutils import _readdir
except ImportError:
    _readdir = None


@pytest.mark.skipif(_readdir is None, reason="extension isn't compiled")
class TestCPyListDir(TestNativeListDir):
    module = _readdir


@pytest.mark.skipif(_readdir is None, reason="extension isn't compiled")
class TestCPyReaddir(TestNativeReaddir):
    module = _readdir


class TestEnsureDirs(TempDir):

    def check_dir(self, path, uid, gid, mode):
        assert os.path.isdir(path)
        st = os.stat(path)
        assert stat.S_IMODE(st.st_mode) == mode, \
            '0%o != 0%o' % (stat.S_IMODE(st.st_mode), mode)
        assert st.st_uid == uid
        assert st.st_gid == gid

    def test_ensure_dirs(self):
        # default settings
        path = pjoin(self.dir, 'foo', 'bar')
        assert osutils.ensure_dirs(path)
        self.check_dir(path, os.geteuid(), os.getegid(), 0o777)

    def test_minimal_nonmodifying(self):
        path = pjoin(self.dir, 'foo', 'bar')
        assert osutils.ensure_dirs(path, mode=0o755)
        os.chmod(path, 0o777)
        assert osutils.ensure_dirs(path, mode=0o755, minimal=True)
        self.check_dir(path, os.geteuid(), os.getegid(), 0o777)

    def test_minimal_modifying(self):
        path = pjoin(self.dir, 'foo', 'bar')
        assert osutils.ensure_dirs(path, mode=0o750)
        assert osutils.ensure_dirs(path, mode=0o005, minimal=True)
        self.check_dir(path, os.geteuid(), os.getegid(), 0o755)

    def test_create_unwritable_subdir(self):
        path = pjoin(self.dir, 'restricted', 'restricted')
        # create the subdirs without 020 first
        assert osutils.ensure_dirs(os.path.dirname(path))
        assert osutils.ensure_dirs(path, mode=0o020)
        self.check_dir(path, os.geteuid(), os.getegid(), 0o020)
        # unrestrict it
        osutils.ensure_dirs(path)
        self.check_dir(path, os.geteuid(), os.getegid(), 0o777)

    def test_path_is_a_file(self):
        # fail if passed a path to an existing file
        path = pjoin(self.dir, 'file')
        touch(path)
        assert os.path.isfile(path)
        assert not osutils.ensure_dirs(path, mode=0o700)

    def test_non_dir_in_path(self):
        # fail if one of the parts of the path isn't a dir
        path = pjoin(self.dir, 'file', 'dir')
        touch(pjoin(self.dir, 'file'))
        assert not osutils.ensure_dirs(path, mode=0o700)

    def test_mkdir_failing(self):
        # fail if os.mkdir fails
        with mock.patch('snakeoil.osutils.os.mkdir') as mkdir:
            mkdir.side_effect = OSError(30, 'Read-only file system')
            path = pjoin(self.dir, 'dir')
            assert not osutils.ensure_dirs(path, mode=0o700)

            # force temp perms
            assert not osutils.ensure_dirs(path, mode=0o400)
            mkdir.side_effect = OSError(17, 'File exists')
            assert not osutils.ensure_dirs(path, mode=0o700)

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
            assert not osutils.ensure_dirs(path, mode=0o005, minimal=True)
            assert not osutils.ensure_dirs(path, mode=0o005, minimal=False)
            os.rmdir(path)

            # chmod failure when resetting perms on parents
            assert not osutils.ensure_dirs(path, mode=0o400)
            os.rmdir(path)

            # chown failure when resetting perms on parents
            chmod.side_effect = None
            chown.side_effect = OSError(5, 'Input/output error')
            assert not osutils.ensure_dirs(path, uid=1000, gid=1000, mode=0o400)

    def test_reset_sticky_parent_perms(self):
        # make sure perms are reset after traversing over sticky parents
        sticky_parent = pjoin(self.dir, 'dir')
        path = pjoin(sticky_parent, 'dir')
        os.mkdir(sticky_parent)
        os.chmod(sticky_parent, 0o2755)
        pre_sticky_parent = os.stat(sticky_parent)
        assert osutils.ensure_dirs(path, mode=0o700)
        post_sticky_parent = os.stat(sticky_parent)
        assert pre_sticky_parent.st_mode == post_sticky_parent.st_mode

    def test_mode(self):
        path = pjoin(self.dir, 'mode', 'mode')
        assert osutils.ensure_dirs(path, mode=0o700)
        self.check_dir(path, os.geteuid(), os.getegid(), 0o700)
        # unrestrict it
        osutils.ensure_dirs(path)
        self.check_dir(path, os.geteuid(), os.getegid(), 0o777)

    def test_gid(self):
        # abuse the portage group as secondary group
        try:
            portage_gid = grp.getgrnam('portage').gr_gid
        except KeyError:
            pytest.skip('the portage group does not exist')
        if portage_gid not in os.getgroups():
            pytest.skip('you are not in the portage group')
        path = pjoin(self.dir, 'group', 'group')
        assert osutils.ensure_dirs(path, gid=portage_gid)
        self.check_dir(path, os.geteuid(), portage_gid, 0o777)
        assert osutils.ensure_dirs(path)
        self.check_dir(path, os.geteuid(), portage_gid, 0o777)
        assert osutils.ensure_dirs(path, gid=os.getegid())
        self.check_dir(path, os.geteuid(), os.getegid(), 0o777)


class TestAbsSymlink(TempDir):

    def test_abssymlink(self):
        target = pjoin(self.dir, 'target')
        linkname = pjoin(self.dir, 'link')
        os.mkdir(target)
        os.symlink('target', linkname)
        assert osutils.abssymlink(linkname) == target


class Test_Native_NormPath:

    func = staticmethod(osutils.native_normpath)

    def test_normpath(self):
        f = self.func

        def check(src, val):
            got = f(src)
            assert got == val, "%r: expected %r, got %r" % (src, val, got)

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

        # explicit unicode and bytes
        check('/tmṕ/föo//../dár', '/tmṕ/dár')
        check(b'/tm\xe1\xb9\x95/f\xc3\xb6o//../d\xc3\xa1r', b'/tm\xe1\xb9\x95/d\xc3\xa1r')
        check('/föó/..', '/')
        check(b'/f\xc3\xb6\xc3\xb3/..', b'/')


@pytest.mark.skipif(osutils.normpath is osutils.native_normpath, reason="extension isn't compiled")
class Test_Cpy_NormPath(Test_Native_NormPath):
    func = staticmethod(osutils.normpath)


@pytest.mark.skipif(osutils.join is osutils.native_join, reason="extension isn't compiled")
class Test_Cpy_Join:

    def test_reimplementation(self):
        vals = [
            [""],
            ["foo"],
            ["", "foo"],
            ["foo", "dar"],
            ["foo", "/bar"],
            ["/bar", "dar"],
            ["/bar", "../dar"],
            ["", "../dar"],
            ["/bár", "dãr"],
            [b"/b\xc3\xa1r", b"d\xc3\xa3r"],
        ]

        for x in vals:
            assert osutils.native_join(*x) == osutils.join(*x), \
                "for %r, expected %r, got %r" % (
                    val, osutils.native_join(*x), osutils.join(*x))


    # proper type checking was done in py3.5
    @pytest.mark.skipif(sys.hexversion < 0x03050000, reason='requires >=py3.5')
    def test_reimplementation_errors(self):
        # various type errors
        errors = [
            [],
            [1],
            ["foo", 1],
            ["foo", "/bar", []],
        ]

        for x in errors:
            with pytest.raises(TypeError):
                osutils.native_join(*x)
            with pytest.raises(TypeError):
                osutils.join(*x)


# TODO: more error condition testing
class TestFsLock(TempDir):

    def test_nonexistent(self):
        with pytest.raises(osutils.NonExistent):
            osutils.FsLock(pjoin(self.dir, 'missing'))

    def test_fslock_read_lock(self):
        path = pjoin(self.dir, 'lockfile-read')
        lock = osutils.FsLock(path, True)
        # do this all non-blocking to avoid hanging tests
        assert lock.acquire_read_lock(False)
        # file should exist now
        with open(path, 'r+') as f:
            # acquire and release a read lock
            fcntl.flock(f, fcntl.LOCK_SH | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN)
            # we can't acquire an exclusive lock
            with pytest.raises(IOError):
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_fslock_release_read_lock(self):
        path = pjoin(self.dir, 'lockfile-release-read')
        lock = osutils.FsLock(path, True)
        # do this all non-blocking to avoid hanging tests
        assert lock.acquire_read_lock(False)
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
        assert lock.acquire_write_lock(False)
        # file should exist now
        with open(path, 'r+') as f:
            with pytest.raises(IOError):
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_fslock_release_write_lock(self):
        path = pjoin(self.dir, 'lockfile-release-write')
        lock = osutils.FsLock(path, True)
        # do this all non-blocking to avoid hanging tests
        # acquire an exclusive/write lock
        assert lock.acquire_write_lock(False)
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
        assert lock.acquire_write_lock(False)
        # downgrade to read lock
        assert lock.acquire_read_lock()
        # file should exist now
        with open(path, 'r+') as f:
            fcntl.flock(f, fcntl.LOCK_SH | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN)
            with pytest.raises(IOError):
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_fslock_release_downgraded_lock(self):
        path = pjoin(self.dir, 'lockfile-release-downgraded')
        lock = osutils.FsLock(path, True)
        # do this all non-blocking to avoid hanging tests
        # acquire an exclusive/write lock
        assert lock.acquire_write_lock(False)
        # downgrade to read lock
        assert lock.acquire_read_lock()
        # and release
        lock.release_read_lock()
        # file should exist now
        with open(path, 'r+') as f:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN)


@pytest.mark.skipif(os.getuid() != 0, reason="these tests must be ran as root")
class TestAccess(TempDir):

    func = staticmethod(osutils.fallback_access)

    def test_fallback(self):
        fp = pjoin(self.dir, 'file')
        # create the file
        touch(fp)
        os.chmod(fp, 000)
        assert not self.func(fp, os.X_OK)
        assert self.func(fp, os.W_OK)
        assert self.func(fp, os.R_OK)
        assert self.func(fp, os.W_OK | os.R_OK)
        assert not self.func(fp, os.W_OK | os.R_OK | os.X_OK)


class Test_unlink_if_exists(TempDir):

    func = staticmethod(osutils.unlink_if_exists)

    def test_it(self):
        f = self.func
        path = pjoin(self.dir, 'target')
        f(path)
        write_file(path, 'w', '')
        f(path)
        assert not os.path.exists(path)
        # and once more for good measure...
        f(path)


class TestSupportedSystems:

    def test_supported_system(self):
        @supported_systems('supported')
        def func():
            return True

        with mock.patch('snakeoil.osutils.sys') as _sys:
            _sys.configure_mock(platform='supported')
            assert func()

    def test_unsupported_system(self):
        @supported_systems('unsupported')
        def func():
            return True

        with pytest.raises(NotImplementedError):
            func()

        # make sure we're iterating through the system params correctly
        with mock.patch('snakeoil.osutils.sys') as _sys:
            _sys.configure_mock(platform='u')
            with pytest.raises(NotImplementedError):
                func()

    def test_multiple_systems(self):
        @supported_systems('darwin', 'linux')
        def func():
            return True

        with mock.patch('snakeoil.osutils.sys') as _sys:
            _sys.configure_mock(platform='nonexistent')
            with pytest.raises(NotImplementedError):
                func()

            for platform in ('linux2', 'darwin'):
                _sys.configure_mock(platform=platform)
                assert func()


@pytest.mark.skipif(not sys.platform.startswith('linux'),
                    reason='supported on Linux only')
class TestMount(TempDir):

    def setup(self):
        self.source = pjoin(self.dir, 'source')
        os.mkdir(self.source)
        self.target = pjoin(self.dir, 'target')
        os.mkdir(self.target)

    def test_args_bytes(self):
        # The initial source, target, and fstype arguments to mount(2) must be
        # byte strings; if they are unicode strings the arguments get mangled
        # leading to errors when the syscall is run. This confirms mount() from
        # snakeoil.osutils always converts the arguments into byte strings.
        for source, target, fstype in ((b'source', b'target', b'fstype'),
                                       ('source', 'target', 'fstype')):
            with mock.patch('snakeoil.osutils.mount.ctypes') as mock_ctypes:
                with pytest.raises(OSError):
                    mount(source, target, fstype, MS_BIND)
                mount_call = next(x for x in mock_ctypes.mock_calls if x[0] == 'CDLL().mount')
                for arg in mount_call[1][0:3]:
                    assert isinstance(arg, bytes)

    def test_missing_dirs(self):
        with pytest.raises(OSError) as cm:
            mount('source', 'target', None, MS_BIND)
        assert cm.value.errno == errno.ENOENT

    @pytest.mark.skipif(os.getuid() == 0, reason='this test must be run as non-root')
    def test_no_perms(self):
        with pytest.raises(OSError) as cm:
            mount(self.source, self.target, None, MS_BIND)
        assert cm.value.errno in (errno.EPERM, errno.EACCES)
        with pytest.raises(OSError) as cm:
            umount(self.target)
        assert cm.value.errno in (errno.EPERM, errno.EINVAL)

    @pytest.mark.skipif(not (os.path.exists('/proc/self/ns/mnt') and os.path.exists('/proc/self/ns/user')),
                   reason='user and mount namespace support required')
    def test_bind_mount(self):
        src_file = pjoin(self.source, 'file')
        bind_file = pjoin(self.target, 'file')
        touch(src_file)

        try:
            with Namespace(user=True, mount=True):
                assert not os.path.exists(bind_file)
                mount(self.source, self.target, None, MS_BIND)
                assert os.path.exists(bind_file)
                umount(self.target)
                assert not os.path.exists(bind_file)
        except PermissionError:
            pytest.skip('No permission to use user and mount namespace')

    @pytest.mark.skipif(not (os.path.exists('/proc/self/ns/mnt') and os.path.exists('/proc/self/ns/user')),
                   reason='user and mount namespace support required')
    def test_lazy_unmount(self):
        src_file = pjoin(self.source, 'file')
        bind_file = pjoin(self.target, 'file')
        touch(src_file)
        with open(src_file, 'w') as f:
            f.write('foo')

        try:
            with Namespace(user=True, mount=True):
                mount(self.source, self.target, None, MS_BIND)
                assert os.path.exists(bind_file)

                with open(bind_file) as f:
                    # can't unmount the target due to the open file
                    with pytest.raises(OSError) as cm:
                        umount(self.target)
                    assert cm.value.errno == errno.EBUSY
                    # lazily unmount instead
                    umount(self.target, MNT_DETACH)
                    # confirm the file doesn't exist in the bind mount anymore
                    assert not os.path.exists(bind_file)
                    # but the file is still accessible to the process
                    assert f.read() == 'foo'

                # trying to reopen causes IOError
                with pytest.raises(IOError) as cm:
                    f = open(bind_file)
                assert cm.value.errno == errno.ENOENT
        except PermissionError:
            pytest.skip('No permission to use user and mount namespace')


Test_cpy_readdir_loaded = mk_cpy_loadable_testcase(
    "snakeoil.osutils._readdir", "snakeoil.osutils", "listdir", "listdir")
Test_cpy_posix_loaded = mk_cpy_loadable_testcase(
    "snakeoil._posix", "snakeoil.osutils", "normpath", "normpath")
