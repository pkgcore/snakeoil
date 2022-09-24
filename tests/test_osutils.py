# -*- coding: utf-8 -*-

import errno
import grp
import os
import stat
import sys
from unittest import mock

import pytest
from snakeoil import osutils
from snakeoil.contexts import Namespace
from snakeoil.fileutils import touch
from snakeoil.osutils import native_readdir, supported_systems, sizeof_fmt
from snakeoil.osutils.mount import MNT_DETACH, MS_BIND, mount, umount


class ReaddirCommon:

    @pytest.fixture
    def subdir(self, tmp_path):
        subdir = tmp_path / 'dir'
        subdir.mkdir()
        (tmp_path / 'file').touch()
        os.mkfifo((tmp_path / 'fifo'))
        return subdir

    def _test_missing(self, tmp_path, funcs):
        for func in funcs:
            pytest.raises(OSError, func, tmp_path / 'spork')


class TestNativeListDir(ReaddirCommon):

    def test_listdir(self, tmp_path, subdir):
        assert set(native_readdir.listdir(tmp_path)) == {'dir', 'fifo', 'file'}
        assert native_readdir.listdir(subdir) == []

    def test_listdir_dirs(self, tmp_path, subdir):
        assert native_readdir.listdir_dirs(tmp_path) == ['dir']
        assert native_readdir.listdir_dirs(subdir) == []

    def test_listdir_files(self, tmp_path, subdir):
        assert native_readdir.listdir_files(tmp_path) == ['file']
        assert native_readdir.listdir_dirs(subdir) == []

    def test_missing(self, tmp_path, subdir):
        return self._test_missing(tmp_path, (
            native_readdir.listdir,
            native_readdir.listdir_dirs,
            native_readdir.listdir_files,
        ))

    def test_dangling_sym(self, tmp_path, subdir):
        (tmp_path / "monkeys").symlink_to("foon")
        assert native_readdir.listdir_files(tmp_path) == ['file']


class TestNativeReaddir(ReaddirCommon):
    # TODO: test char/block devices and sockets, devices might be a bit hard
    # because it seems like you need to be root to create them in linux

    def test_readdir(self, tmp_path, subdir):
        (tmp_path / "monkeys").symlink_to("foon")
        (tmp_path / "sym").symlink_to(tmp_path / "file")
        expected = {
            ("dir", "directory"),
            ("file", "file"),
            ("fifo", "fifo"),
            ("monkeys", "symlink"),
            ("sym", "symlink"),
        }
        assert set(native_readdir.readdir(tmp_path)) == expected
        assert native_readdir.readdir(subdir) == []

    def test_missing(self, tmp_path):
        return self._test_missing(tmp_path, (native_readdir.readdir,))


class TestEnsureDirs:

    def check_dir(self, path, uid, gid, mode):
        assert path.is_dir()
        st = os.stat(path)
        assert stat.S_IMODE(st.st_mode) == mode, \
            '0%o != 0%o' % (stat.S_IMODE(st.st_mode), mode)
        assert st.st_uid == uid
        assert st.st_gid == gid

    def test_ensure_dirs(self, tmp_path):
        # default settings
        path = tmp_path / 'foo' / 'bar'
        assert osutils.ensure_dirs(path)
        self.check_dir(path, os.geteuid(), os.getegid(), 0o777)

    def test_minimal_nonmodifying(self, tmp_path):
        path = tmp_path / 'foo' / 'bar'
        assert osutils.ensure_dirs(path, mode=0o755)
        os.chmod(path, 0o777)
        assert osutils.ensure_dirs(path, mode=0o755, minimal=True)
        self.check_dir(path, os.geteuid(), os.getegid(), 0o777)

    def test_minimal_modifying(self, tmp_path):
        path = tmp_path / 'foo' / 'bar'
        assert osutils.ensure_dirs(path, mode=0o750)
        assert osutils.ensure_dirs(path, mode=0o005, minimal=True)
        self.check_dir(path, os.geteuid(), os.getegid(), 0o755)

    def test_create_unwritable_subdir(self, tmp_path):
        path = tmp_path / 'restricted' / 'restricted'
        # create the subdirs without 020 first
        assert osutils.ensure_dirs(path.parent)
        assert osutils.ensure_dirs(path, mode=0o020)
        self.check_dir(path, os.geteuid(), os.getegid(), 0o020)
        # unrestrict it
        osutils.ensure_dirs(path)
        self.check_dir(path, os.geteuid(), os.getegid(), 0o777)

    def test_path_is_a_file(self, tmp_path):
        # fail if passed a path to an existing file
        path = tmp_path / 'file'
        touch(path)
        assert path.is_file()
        assert not osutils.ensure_dirs(path, mode=0o700)

    def test_non_dir_in_path(self, tmp_path):
        # fail if one of the parts of the path isn't a dir
        path = tmp_path / 'file' / 'dir'
        (tmp_path / 'file').touch()
        assert not osutils.ensure_dirs(path, mode=0o700)

    def test_mkdir_failing(self, tmp_path):
        # fail if os.mkdir fails
        with mock.patch('snakeoil.osutils.os.mkdir') as mkdir:
            mkdir.side_effect = OSError(30, 'Read-only file system')
            path = tmp_path / 'dir'
            assert not osutils.ensure_dirs(path, mode=0o700)

            # force temp perms
            assert not osutils.ensure_dirs(path, mode=0o400)
            mkdir.side_effect = OSError(17, 'File exists')
            assert not osutils.ensure_dirs(path, mode=0o700)

    def test_chmod_or_chown_failing(self, tmp_path):
        # fail if chmod or chown fails
        path = tmp_path / 'dir'
        path.mkdir()
        path.chmod(0o750)

        with mock.patch('snakeoil.osutils.os.chmod') as chmod, \
                mock.patch('snakeoil.osutils.os.chown') as chown:
            chmod.side_effect = OSError(5, 'Input/output error')

            # chmod failure when file exists and trying to reset perms to match
            # the specified mode
            assert not osutils.ensure_dirs(path, mode=0o005, minimal=True)
            assert not osutils.ensure_dirs(path, mode=0o005, minimal=False)
            path.rmdir()

            # chmod failure when resetting perms on parents
            assert not osutils.ensure_dirs(path, mode=0o400)
            path.rmdir()

            # chown failure when resetting perms on parents
            chmod.side_effect = None
            chown.side_effect = OSError(5, 'Input/output error')
            assert not osutils.ensure_dirs(path, uid=1000, gid=1000, mode=0o400)

    def test_reset_sticky_parent_perms(self, tmp_path):
        # make sure perms are reset after traversing over sticky parents
        sticky_parent = tmp_path / 'dir'
        path = sticky_parent / 'dir'
        sticky_parent.mkdir()
        sticky_parent.chmod(0o2755)
        pre_sticky_parent = os.stat(sticky_parent)
        assert osutils.ensure_dirs(path, mode=0o700)
        post_sticky_parent = os.stat(sticky_parent)
        assert pre_sticky_parent.st_mode == post_sticky_parent.st_mode

    def test_mode(self, tmp_path):
        path = tmp_path / 'mode' / 'mode'
        assert osutils.ensure_dirs(path, mode=0o700)
        self.check_dir(path, os.geteuid(), os.getegid(), 0o700)
        # unrestrict it
        osutils.ensure_dirs(path)
        self.check_dir(path, os.geteuid(), os.getegid(), 0o777)

    def test_gid(self, tmp_path):
        # abuse the portage group as secondary group
        try:
            portage_gid = grp.getgrnam('portage').gr_gid
        except KeyError:
            pytest.skip('the portage group does not exist')
        if portage_gid not in os.getgroups():
            pytest.skip('you are not in the portage group')
        path = tmp_path / 'group' / 'group'
        assert osutils.ensure_dirs(path, gid=portage_gid)
        self.check_dir(path, os.geteuid(), portage_gid, 0o777)
        assert osutils.ensure_dirs(path)
        self.check_dir(path, os.geteuid(), portage_gid, 0o777)
        assert osutils.ensure_dirs(path, gid=os.getegid())
        self.check_dir(path, os.geteuid(), os.getegid(), 0o777)


class TestAbsSymlink:

    def test_abssymlink(self, tmp_path):
        target = tmp_path / 'target'
        linkname = tmp_path / 'link'
        target.mkdir()
        linkname.symlink_to('target')
        assert osutils.abssymlink(linkname) == str(target)


class Test_Native_NormPath:

    func = staticmethod(osutils.normpath)

    def test_normpath(self):
        f = self.func

        def check(src, val):
            got = f(src)
            assert got == val, f"{src!r}: expected {val!r}, got {got!r}"

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


@pytest.mark.skipif(os.getuid() != 0, reason="these tests must be ran as root")
class TestAccess:

    func = staticmethod(osutils.fallback_access)

    def test_fallback(self, tmp_path):
        fp = tmp_path / 'file'
        # create the file
        fp.touch()
        fp.chmod(0o000)
        assert not self.func(fp, os.X_OK)
        assert self.func(fp, os.W_OK)
        assert self.func(fp, os.R_OK)
        assert self.func(fp, os.W_OK | os.R_OK)
        assert not self.func(fp, os.W_OK | os.R_OK | os.X_OK)


class Test_unlink_if_exists:

    func = staticmethod(osutils.unlink_if_exists)

    def test_it(self, tmp_path):
        f = self.func
        path = tmp_path / 'target'
        f(path)
        path.write_text('')
        f(path)
        assert not path.exists()
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
class TestMount:

    @pytest.fixture
    def source(self, tmp_path):
        source = tmp_path / 'source'
        source.mkdir()
        return source

    @pytest.fixture
    def target(self, tmp_path):
        target = tmp_path / 'target'
        target.mkdir()
        return target

    def test_args_bytes(self):
        # The initial source, target, and fstype arguments to mount(2) must be
        # byte strings; if they are unicode strings the arguments get mangled
        # leading to errors when the syscall is run. This confirms mount() from
        # snakeoil.osutils always converts the arguments into byte strings.
        for source, target, fstype in ((b'source', b'target', b'fstype'),
                                       ('source', 'target', 'fstype')):
            with mock.patch('snakeoil.osutils.mount.ctypes') as mock_ctypes:
                with pytest.raises(OSError):
                    mount(str(source), str(target), fstype, MS_BIND)
                mount_call = next(x for x in mock_ctypes.mock_calls if x[0] == 'CDLL().mount')
                for arg in mount_call[1][0:3]:
                    assert isinstance(arg, bytes)

    def test_missing_dirs(self):
        with pytest.raises(OSError) as cm:
            mount('source', 'target', None, MS_BIND)
        assert cm.value.errno in (errno.EPERM, errno.ENOENT)

    @pytest.mark.skipif(os.getuid() == 0, reason='this test must be run as non-root')
    def test_no_perms(self, source, target):
        with pytest.raises(OSError) as cm:
            mount(str(source), str(target), None, MS_BIND)
        assert cm.value.errno in (errno.EPERM, errno.EACCES)
        with pytest.raises(OSError) as cm:
            umount(str(target))
        assert cm.value.errno in (errno.EPERM, errno.EINVAL)

    @pytest.mark.skipif(not (os.path.exists('/proc/self/ns/mnt') and os.path.exists('/proc/self/ns/user')),
                        reason='user and mount namespace support required')
    def test_bind_mount(self, source, target):
        src_file = source / 'file'
        bind_file = target / 'file'
        src_file.touch()

        try:
            with Namespace(user=True, mount=True):
                assert not bind_file.exists()
                mount(str(source), str(target), None, MS_BIND)
                assert bind_file.exists()
                umount(str(target))
                assert not bind_file.exists()
        except PermissionError:
            pytest.skip('No permission to use user and mount namespace')

    @pytest.mark.skipif(not (os.path.exists('/proc/self/ns/mnt') and os.path.exists('/proc/self/ns/user')),
                   reason='user and mount namespace support required')
    def test_lazy_unmount(self, source, target):
        src_file = source / 'file'
        bind_file = target / 'file'
        src_file.touch()
        src_file.write_text('foo')

        try:
            with Namespace(user=True, mount=True):
                mount(str(source), str(target), None, MS_BIND)
                assert bind_file.exists()

                with bind_file.open() as f:
                    # can't unmount the target due to the open file
                    with pytest.raises(OSError) as cm:
                        umount(str(target))
                    assert cm.value.errno == errno.EBUSY
                    # lazily unmount instead
                    umount(str(target), MNT_DETACH)
                    # confirm the file doesn't exist in the bind mount anymore
                    assert not bind_file.exists()
                    # but the file is still accessible to the process
                    assert f.read() == 'foo'

                # trying to reopen causes IOError
                with pytest.raises(IOError) as cm:
                    f = bind_file.open()
                assert cm.value.errno == errno.ENOENT
        except PermissionError:
            pytest.skip('No permission to use user and mount namespace')


class TestSizeofFmt:
    expected = {
        0: ("0.0 B", "0.0 B"),
        1: ("1.0 B", "1.0 B"),
        1000: ("1.0 kB", "1000.0 B"),
        1024: ("1.0 kB", "1.0 KiB"),
        1000**2: ("1.0 MB", "976.6 KiB"),
        1024**2: ("1.0 MB", "1.0 MiB"),
        1000**3: ("1.0 GB", "953.7 MiB"),
        1024**3: ("1.1 GB", "1.0 GiB"),
        1000**8: ("1.0 YB", "847.0 ZiB"),
        1024**8: ("1.2 YB", "1.0 YiB"),
        1000**9: ("1000.0 YB", "827.2 YiB"),
        1024**9: ("1237.9 YB", "1024.0 YiB"),
    }

    @pytest.mark.parametrize("binary", (False, True))
    @pytest.mark.parametrize("size", sorted(expected))
    def test_sizeof_fmt(self, size, binary):
        assert sizeof_fmt(size, binary=binary) == self.expected[size][binary]
