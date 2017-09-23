# Copyright: 2010-2011 Brian Harring <ferringb@gmail.com>
# Copyright: 2005 Marien Zwart <marienz@gentoo.org>
# License: BSD/GPL2

import errno
import mmap
import os
import time

pjoin = os.path.join

from snakeoil import compatibility, currying, fileutils, _fileutils
from snakeoil.fileutils import AtomicWriteFile
from snakeoil.test import TestCase, not_a_test, SkipTest
from snakeoil.test.mixins import TempDirMixin


class TestTouch(TempDirMixin):

    def test_file_creation(self):
        fp = pjoin(self.dir, 'file')
        orig_um = os.umask(0o000)
        try:
            fileutils.touch(fp)
        finally:
            exiting_umask = os.umask(orig_um)
        self.assertEqual(exiting_umask, 0o000)
        self.assertEqual(os.path.exists(fp), True)
        self.assertEqual(os.stat(fp).st_mode & 0o4777, 0o644)

    def test_set_times(self):
        fp = pjoin(self.dir, 'file')
        fileutils.touch(fp)
        orig_stat = os.stat(fp)
        time.sleep(1)
        fileutils.touch(fp)
        new_stat = os.stat(fp)
        self.assertNotEqual(orig_stat.st_atime, new_stat.st_atime)
        self.assertNotEqual(orig_stat.st_mtime, new_stat.st_mtime)

    def test_set_custom_times(self):
        fp = pjoin(self.dir, 'file')
        fileutils.touch(fp)
        orig_stat = os.stat(fp)
        times = (1, 1)
        fileutils.touch(fp, times=times)
        new_stat = os.stat(fp)
        self.assertNotEqual(orig_stat, new_stat)
        self.assertEqual(1, new_stat.st_atime)
        self.assertEqual(1, new_stat.st_mtime)

    def test_set_custom_nstimes(self):
        if not compatibility.is_py3k:
            raise SkipTest('requires py33 and up')

        fp = pjoin(self.dir, 'file')
        fileutils.touch(fp)
        orig_stat = os.stat(fp)
        ns = (1, 1)
        fileutils.touch(fp, ns=ns)
        new_stat = os.stat(fp)
        self.assertNotEqual(orig_stat, new_stat)
        self.assertEqual(1, new_stat.st_atime_ns)
        self.assertEqual(1, new_stat.st_mtime_ns)


class TestAtomicWriteFile(TempDirMixin):

    kls = AtomicWriteFile

    def test_normal_ops(self):
        fp = pjoin(self.dir, "target")
        self.write_file(fp, "w", "me")
        af = self.kls(fp)
        af.write("dar")
        self.assertEqual(fileutils.readfile_ascii(fp), "me")
        af.close()
        self.assertEqual(fileutils.readfile_ascii(fp), "dar")

    def test_perms(self):
        fp = pjoin(self.dir, 'target')
        orig_um = os.umask(0o777)
        try:
            af = self.kls(fp, perms=0o644)
            af.write("dar")
            af.close()
        finally:
            exiting_umask = os.umask(orig_um)
        self.assertEqual(exiting_umask, 0o777)
        self.assertEqual(os.stat(fp).st_mode & 0o4777, 0o644)

    def test_del(self):
        fp = pjoin(self.dir, "target")
        self.write_file(fp, "w", "me")
        self.assertEqual(fileutils.readfile_ascii(fp), "me")
        af = self.kls(fp)
        af.write("dar")
        del af
        self.assertEqual(fileutils.readfile_ascii(fp), "me")
        self.assertEqual(len(os.listdir(self.dir)), 1)

    def test_close(self):
        # verify that we handle multiple closes; no exception is good.
        af = self.kls(pjoin(self.dir, "target"))
        af.close()
        af.close()

    def test_discard(self):
        fp = pjoin(self.dir, "target")
        self.write_file(fp, "w", "me")
        self.assertEqual(fileutils.readfile_ascii(fp), "me")
        af = self.kls(fp)
        af.write("dar")
        af.discard()
        self.assertFalse(os.path.exists(af._temp_fp))
        af.close()
        self.assertEqual(fileutils.readfile_ascii(fp), "me")

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

class native_readfile_Test(TempDirMixin):
    func = staticmethod(fileutils.native_readfile)

    test_cases = ['asdf\nfdasswer\1923', '', '987234']

    default_encoding = 'ascii'
    none_on_missing_ret_data = 'dar'

    @staticmethod
    def convert_data(data, encoding):
        if compatibility.is_py3k:
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
            self.write_file(fp, 'wb',
                            self.convert_data(expected, encoding))
            if raised:
                self.assertRaises(raised, self.assertFunc, fp, expected)
            else:
                self.assertFunc(fp, expected)

    def assertFunc(self, path, expected):
        self.assertEqual(self.func(path), expected)

    def test_none_on_missing(self):
        fp = pjoin(self.dir, 'nonexistent')
        self.assertRaises(EnvironmentError, self.func, fp)
        self.assertEqual(self.func(fp, True), None)
        self.write_file(fp, 'wb', self.convert_data('dar', 'ascii'))
        self.assertEqual(self.func(fp, True), self.none_on_missing_ret_data)

        # ensure it handles paths that go through files-
        # still should be suppress
        self.assertEqual(self.func(pjoin(fp, 'extra'), True), None)


class cpy_readfile_Test(native_readfile_Test):
    cpy_setup_class(locals(), 'readfile')


class native_readfile_ascii_Test(native_readfile_Test):
    func = staticmethod(fileutils.native_readfile_ascii)


class cpy_readfile_ascii_Test(native_readfile_ascii_Test):
    cpy_setup_class(locals(), 'readfile_ascii')


class native_readfile_ascii_strict_Test(native_readfile_ascii_Test):
    func = staticmethod(fileutils.native_readfile_ascii_strict)
    test_cases = native_readfile_ascii_Test.test_cases + [
        (u'\xf2', 'latin', (ValueError, UnicodeDecodeError)),
        (u'\ua000', 'utf8', UnicodeDecodeError),
        ]

class cpy_readfile_ascii_strict_Test(native_readfile_ascii_strict_Test):
    cpy_setup_class(locals(), 'readfile_ascii_strict')


class native_readfile_utf8_Test(native_readfile_Test):
    func = staticmethod(fileutils.native_readfile_utf8)
    default_encoding = 'utf8'

class cpy_readfile_utf8_Test(native_readfile_utf8_Test):
    cpy_setup_class(locals(), 'readfile_utf8')

class native_readfile_utf8_strict_Test(native_readfile_Test):
    func = staticmethod(fileutils.native_readfile_utf8_strict)
    default_encoding = 'utf8'
    test_cases = native_readfile_ascii_Test.test_cases + [
        u'\ua000fa',
        ]

class cpy_readfile_utf8_strict_Test(native_readfile_utf8_Test):
    cpy_setup_class(locals(), 'readfile_utf8_strict')

class native_readfile_bytes_Test(native_readfile_Test):
    func = staticmethod(fileutils.native_readfile_bytes)
    default_encoding = None
    test_cases = map(
        currying.post_curry(native_readfile_Test.convert_data, 'ascii'),
        native_readfile_Test.test_cases)
    test_cases.append(u'\ua000fa'.encode("utf8"))
    none_on_missing_ret_data = native_readfile_Test.convert_data(
        native_readfile_Test.none_on_missing_ret_data, 'ascii')


class readlines_mixin(object):

    def assertFunc(self, path, expected):
        expected = tuple(expected.split())
        if expected == ('',):
            expected = ()

        if 'utf8' not in self.encoding_mode:
            self.assertEqual(tuple(self.func(path)), expected)
            return
        data = tuple(self.func(path))
        if 'strict' not in self.encoding_mode and not compatibility.is_py3k:
            data = tuple(x.decode() for x in data)
        self.assertEqual(data, expected)

    def test_none_on_missing(self):
        fp = pjoin(self.dir, 'nonexistent')
        self.assertRaises(EnvironmentError, self.func, fp)
        self.assertEqual(tuple(self.func(fp, False, True)), ())
        self.write_file(fp, 'wb', self.convert_data('dar', 'ascii'))
        self.assertEqual(tuple(self.func(fp, True)),
                         (self.none_on_missing_ret_data,))

        self.assertEqual(tuple(self.func(pjoin(fp, 'missing'), False, True)), ())


    def test_strip_whitespace(self):
        fp = pjoin(self.dir, 'data')

        self.write_file(fp, 'wb', self.convert_data(' dar1 \ndar2 \n dar3\n',
                                                    'ascii'))
        results = tuple(self.func(fp, True))
        expected = ('dar1', 'dar2', 'dar3')
        if self.encoding_mode == 'bytes' and compatibility.is_py3k:
            expected = tuple(x.encode("ascii") for x in expected)
        self.assertEqual(results, expected)

        # this time without the trailing newline...
        self.write_file(fp, 'wb', self.convert_data(' dar1 \ndar2 \n dar3',
                                                    'ascii'))
        results = tuple(self.func(fp, True))
        self.assertEqual(results, expected)


        # test a couple of edgecases; underly c extension has gotten these
        # wrong before.
        self.write_file(fp, 'wb', self.convert_data('0', 'ascii'))
        results = tuple(self.func(fp, True))
        expected = ('0',)
        if self.encoding_mode == 'bytes' and compatibility.is_py3k:
            expected = tuple(x.encode("ascii") for x in expected)
        self.assertEqual(results, expected)

        self.write_file(fp, 'wb', self.convert_data('0\n', 'ascii'))
        results = tuple(self.func(fp, True))
        expected = ('0',)
        if self.encoding_mode == 'bytes' and compatibility.is_py3k:
            expected = tuple(x.encode("ascii") for x in expected)
        self.assertEqual(results, expected)

        self.write_file(fp, 'wb', self.convert_data('0 ', 'ascii'))
        results = tuple(self.func(fp, True))
        expected = ('0',)
        if self.encoding_mode == 'bytes' and compatibility.is_py3k:
            expected = tuple(x.encode("ascii") for x in expected)
        self.assertEqual(results, expected)


@not_a_test
def mk_readlines_test(scope, mode):
    func_name = 'readlines_%s' % mode
    base = globals()['native_readfile_%s_Test' % mode]

    class kls(readlines_mixin, base):
        func = staticmethod(getattr(fileutils, func_name))
        encoding_mode = mode

    kls.__name__ = "%s_Test" % func_name
    scope["%s_Test" % func_name] = kls

for case in ("ascii", "ascii_strict", "bytes", "utf8"):
    name = 'readlines_%s' % case
    mk_readlines_test(locals(), case)


class TestBrokenStats(TestCase):

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

        self.assertEqual(func_data, data)


class mmap_or_open_for_read(TempDirMixin, TestCase):

    func = staticmethod(fileutils.mmap_or_open_for_read)

    def test_zero_length(self):
        path = pjoin(self.dir, 'target')
        self.write_file(path, 'w', '')
        m, f = self.func(path)
        self.assertIdentical(m, None)
        self.assertEqual(f.read(), b'')
        f.close()

    def test_mmap(self, data=b'foonani'):
        path = pjoin(self.dir, 'target')
        self.write_file(path, 'wb', data)
        m, f = self.func(path)
        self.assertEqual(len(m), len(data))
        self.assertEqual(m.read(len(data)), data)
        m.close()
        self.assertIdentical(f, None)


class Test_mmap_and_close(TempDirMixin):

    def test_it(self):
        path = pjoin(self.dir, 'target')
        data = b'asdfasdf'
        self.write_file(path, 'wb', [data])
        fd, m = None, None
        try:
            fd = os.open(path, os.O_RDONLY)
            m = _fileutils.mmap_and_close(
                fd, len(data), mmap.MAP_PRIVATE, mmap.PROT_READ)
            # and ensure it closed the fd...
            self.assertRaises(EnvironmentError, os.read, fd, 1)
            fd = None
            self.assertEqual(len(m), len(data))
            self.assertEqual(m.read(len(data)), data)
        finally:
            if m is not None:
                m.close()
            if fd is not None:
                os.close(fd)
