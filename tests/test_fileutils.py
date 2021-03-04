import errno
import mmap
import os
import time

pjoin = os.path.join

import pytest

from snakeoil import currying, fileutils, _fileutils
from snakeoil.fileutils import AtomicWriteFile, write_file
from snakeoil.test.fixtures import RandomPath, TempDir


class TestTouch(RandomPath):

    def test_file_creation(self):
        orig_um = os.umask(0o000)
        try:
            fileutils.touch(self.path)
        finally:
            exiting_umask = os.umask(orig_um)
        assert exiting_umask == 0o000
        assert os.path.exists(self.path)
        assert os.stat(self.path).st_mode & 0o4777 == 0o644

    def test_set_times(self):
        fileutils.touch(self.path)
        orig_stat = os.stat(self.path)
        time.sleep(1)
        fileutils.touch(self.path)
        new_stat = os.stat(self.path)
        assert orig_stat.st_atime != new_stat.st_atime
        assert orig_stat.st_mtime != new_stat.st_mtime

    def test_set_custom_times(self):
        fileutils.touch(self.path)
        orig_stat = os.stat(self.path)
        times = (1, 1)
        fileutils.touch(self.path, times=times)
        new_stat = os.stat(self.path)
        assert orig_stat != new_stat
        assert 1 == new_stat.st_atime
        assert 1 == new_stat.st_mtime

    def test_set_custom_nstimes(self):
        fileutils.touch(self.path)
        orig_stat = os.stat(self.path)
        ns = (1, 1)
        fileutils.touch(self.path, ns=ns)
        new_stat = os.stat(self.path)

        # system doesn't have nanosecond precision, try microseconds
        if new_stat.st_atime == 0:
            ns = (1000, 1000)
            fileutils.touch(self.path, ns=ns)
            new_stat = os.stat(self.path)

        assert orig_stat != new_stat
        assert ns[0] == new_stat.st_atime_ns
        assert ns[0] == new_stat.st_mtime_ns


class TestAtomicWriteFile(TempDir):

    kls = AtomicWriteFile

    def test_normal_ops(self):
        fp = pjoin(self.dir, "target")
        write_file(fp, "w", "me")
        af = self.kls(fp)
        af.write("dar")
        assert fileutils.readfile_ascii(fp) == "me"
        af.close()
        assert fileutils.readfile_ascii(fp) == "dar"

    def test_perms(self):
        fp = pjoin(self.dir, 'target')
        orig_um = os.umask(0o777)
        try:
            af = self.kls(fp, perms=0o644)
            af.write("dar")
            af.close()
        finally:
            exiting_umask = os.umask(orig_um)
        assert exiting_umask == 0o777
        assert os.stat(fp).st_mode & 0o4777 == 0o644

    def test_del(self):
        fp = pjoin(self.dir, "target")
        write_file(fp, "w", "me")
        assert fileutils.readfile_ascii(fp) == "me"
        af = self.kls(fp)
        af.write("dar")
        del af
        assert fileutils.readfile_ascii(fp) == "me"
        assert len(os.listdir(self.dir)) == 1

    def test_close(self):
        # verify that we handle multiple closes; no exception is good.
        af = self.kls(pjoin(self.dir, "target"))
        af.close()
        af.close()

    def test_discard(self):
        fp = pjoin(self.dir, "target")
        write_file(fp, "w", "me")
        assert fileutils.readfile_ascii(fp) == "me"
        af = self.kls(fp)
        af.write("dar")
        af.discard()
        assert not os.path.exists(af._temp_fp)
        af.close()
        assert fileutils.readfile_ascii(fp) == "me"

        # finally validate that it handles multiple discards properly.
        af = self.kls(fp)
        af.write("dar")
        af.discard()
        af.discard()
        af.close()


def cpy_setup_class(scope, func_name):
    if getattr(fileutils, 'native_%s' % func_name) \
        is getattr(fileutils, func_name):
        scope['skip'] = 'extensions disabled'
    else:
        scope['func'] = staticmethod(getattr(fileutils, func_name))

class Test_readfile(TempDir):
    func = staticmethod(fileutils.readfile)

    test_cases = ['asdf\nfdasswer\1923', '', '987234']

    default_encoding = 'ascii'
    none_on_missing_ret_data = 'dar'

    @staticmethod
    def convert_data(data, encoding):
        if isinstance(data, bytes):
            return data
        if encoding:
            return data.encode(encoding)
        return data

    def test_it(self):
        fp = pjoin(self.dir, 'testfile')
        for expected in self.test_cases:
            raised = None
            encoding = self.default_encoding
            if isinstance(expected, tuple):
                if len(expected) == 3:
                    raised = expected[2]
                if expected[1] is not None:
                    encoding = expected[1]
                expected = expected[0]
            write_file(fp, 'wb', self.convert_data(expected, encoding))
            if raised:
                with pytest.raises(raised):
                    self.assertFunc(fp, expected)
            else:
                self.assertFunc(fp, expected)

    def assertFunc(self, path, expected):
        assert self.func(path) == expected

    def test_none_on_missing(self):
        fp = pjoin(self.dir, 'nonexistent')
        with pytest.raises(FileNotFoundError):
            self.func(fp)
        assert self.func(fp, True) == None
        write_file(fp, 'wb', self.convert_data('dar', 'ascii'))
        assert self.func(fp, True) == self.none_on_missing_ret_data

        # ensure it handles paths that go through files-
        # still should be suppress
        assert self.func(pjoin(fp, 'extra'), True) == None


class Test_readfile_ascii(Test_readfile):
    func = staticmethod(fileutils.readfile_ascii)


class Test_readfile_utf8(Test_readfile):
    func = staticmethod(fileutils.readfile_utf8)
    default_encoding = 'utf8'


class Test_readfile_bytes(Test_readfile):
    func = staticmethod(fileutils.readfile_bytes)
    default_encoding = None
    test_cases = list(map(
        currying.post_curry(Test_readfile.convert_data, 'ascii'),
        Test_readfile.test_cases))
    test_cases.append('\ua000fa'.encode("utf8"))
    none_on_missing_ret_data = Test_readfile.convert_data(
        Test_readfile.none_on_missing_ret_data, 'ascii')


class readlines_mixin(TempDir):

    def assertFunc(self, path, expected):
        expected = tuple(expected.split())
        if expected == ('',):
            expected = ()

        if 'utf8' not in self.encoding_mode:
            assert tuple(self.func(path)) == expected
            return
        data = tuple(self.func(path))
        assert data == expected

    def test_none_on_missing(self):
        fp = pjoin(self.dir, 'nonexistent')
        with pytest.raises(FileNotFoundError):
            self.func(fp)
        assert tuple(self.func(fp, False, True)) == ()
        write_file(fp, 'wb', self.convert_data('dar', 'ascii'))
        assert tuple(self.func(fp, True)) == (self.none_on_missing_ret_data,)
        assert tuple(self.func(pjoin(fp, 'missing'), False, True)) == ()

    def test_strip_whitespace(self):
        fp = pjoin(self.dir, 'data')

        write_file(fp, 'wb', self.convert_data(' dar1 \ndar2 \n dar3\n',
                                                    'ascii'))
        results = tuple(self.func(fp, True))
        expected = ('dar1', 'dar2', 'dar3')
        if self.encoding_mode == 'bytes':
            expected = tuple(x.encode("ascii") for x in expected)
        assert results == expected

        # this time without the trailing newline...
        write_file(fp, 'wb', self.convert_data(' dar1 \ndar2 \n dar3',
                                                    'ascii'))
        results = tuple(self.func(fp, True))
        assert results == expected

        # test a couple of edgecases; underly c extension has gotten these
        # wrong before.
        write_file(fp, 'wb', self.convert_data('0', 'ascii'))
        results = tuple(self.func(fp, True))
        expected = ('0',)
        if self.encoding_mode == 'bytes':
            expected = tuple(x.encode("ascii") for x in expected)
        assert results == expected

        write_file(fp, 'wb', self.convert_data('0\n', 'ascii'))
        results = tuple(self.func(fp, True))
        expected = ('0',)
        if self.encoding_mode == 'bytes':
            expected = tuple(x.encode("ascii") for x in expected)
        assert results == expected

        write_file(fp, 'wb', self.convert_data('0 ', 'ascii'))
        results = tuple(self.func(fp, True))
        expected = ('0',)
        if self.encoding_mode == 'bytes':
            expected = tuple(x.encode("ascii") for x in expected)
        assert results == expected


def mk_readlines_test(scope, mode):
    func_name = 'readlines_%s' % mode
    base = globals()['Test_readfile_%s' % mode]

    class kls(readlines_mixin, base):
        func = staticmethod(getattr(fileutils, func_name))
        encoding_mode = mode

    kls.__name__ = "Test_%s" % func_name
    scope["Test_%s" % func_name] = kls

for case in ("ascii", "bytes", "utf8"):
    name = 'readlines_%s' % case
    mk_readlines_test(locals(), case)


class TestBrokenStats:

    test_cases = ['/proc/crypto', '/sys/devices/system/cpu/present']

    def test_readfile(self):
        for path in self.test_cases:
            self._check_path(path, fileutils.readfile)

    def test_readlines(self):
        for path in self.test_cases:
            self._check_path(path, fileutils.readlines, True)

    def _check_path(self, path, func, split_it=False):
        try:
            with open(path, 'r') as handle:
                data = handle.read()
        except EnvironmentError as e:
            if e.errno not in (errno.ENOENT, errno.EPERM):
                raise
            return

        func_data = func(path)
        if split_it:
            func_data = list(func_data)
            data = [x for x in data.split('\n') if x]
            func_data = [x for x in func_data if x]

        assert func_data == data


class Test_mmap_or_open_for_read(TempDir):

    func = staticmethod(fileutils.mmap_or_open_for_read)

    def test_zero_length(self):
        path = pjoin(self.dir, 'target')
        write_file(path, 'w', '')
        m, f = self.func(path)
        assert m is None
        assert f.read() == b''
        f.close()

    def test_mmap(self, data=b'foonani'):
        path = pjoin(self.dir, 'target')
        write_file(path, 'wb', data)
        m, f = self.func(path)
        assert len(m) == len(data)
        assert m.read(len(data)) == data
        m.close()
        assert f is None


class Test_mmap_and_close(TempDir):

    def test_it(self):
        path = pjoin(self.dir, 'target')
        data = b'asdfasdf'
        write_file(path, 'wb', [data])
        fd, m = None, None
        try:
            fd = os.open(path, os.O_RDONLY)
            m = _fileutils.mmap_and_close(
                fd, len(data), mmap.MAP_PRIVATE, mmap.PROT_READ)
            # and ensure it closed the fd...
            with pytest.raises(EnvironmentError):
                os.read(fd, 1)
            fd = None
            assert len(m) == len(data)
            assert m.read(len(data)) == data
        finally:
            if m is not None:
                m.close()
            if fd is not None:
                os.close(fd)
