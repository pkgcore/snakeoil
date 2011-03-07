# Copyright: 2005-2009 Brian Harring <ferringb@gmail.com>
# Copyright: 2006 Marien Zwart <marienz@gentoo.org>
# License: BSD/GPL2

import os
pjoin = os.path.join
import grp
import stat
import fcntl
import codecs

from snakeoil.test import TestCase, SkipTest, mk_cpy_loadable_testcase
from snakeoil import osutils, compatibility, currying
from snakeoil.osutils import native_readdir
from snakeoil.test.mixins import TempDirMixin


class ReaddirCommon(TempDirMixin):

    module = native_readdir

    def setUp(self):
        TempDirMixin.setUp(self)
        self.subdir = pjoin(self.dir, 'dir')
        os.mkdir(self.subdir)
        f = open(pjoin(self.dir, 'file'), 'w')
        f.close()
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
        self.assertEquals(set([
            ("dir", "directory"),
            ("file", "file"),
            ("fifo", "fifo"),
            ("monkeys", "symlink"),
            ("sym", "symlink"),
        ]), set(self.module.readdir(self.dir)))
        self.assertEquals([], self.module.readdir(self.subdir))

    def test_missing(self):
        return self._test_missing((self.module.readdir,))

try:
    # No name "readdir" in module osutils
    # pylint: disable-msg=E0611
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
            self.assertEqual(got, val, msg="%r: expected %r, got %r" %
                (src, val, got))

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
        self.assertEqual(osutils.native_join(*val),
            osutils.join(*val),
            msg="for %r, expected %r, got %r" % (val,
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

    def test_nonexistant(self):
        self.assertRaises(osutils.NonExistant, osutils.FsLock,
            pjoin(self.dir, 'missing'))

    def test_locking(self):
        path = pjoin(self.dir, 'lockfile')
        lock = osutils.FsLock(path, True)
        # do this all non-blocking to avoid hanging tests
        self.assertTrue(lock.acquire_read_lock(False))
        # file should exist now
        f = open(path)
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

def cpy_setup_class(scope, func_name):
    if getattr(osutils, 'native_%s' % func_name) \
        is getattr(osutils, func_name):
        scope['skip'] = 'extensions disabled'
    else:
        scope['func'] = staticmethod(getattr(osutils, func_name))


class native_readfile_Test(TempDirMixin):
    func = staticmethod(osutils.native_readfile)

    test_cases = ['asdf\nfdasswer\1923',
        '',
        '987234']

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
            open(fp, 'wb').write(
                self.convert_data(expected, encoding))
            if raised:
                self.assertRaises(raised, self.assertFunc, fp, expected)
            else:
                self.assertFunc(fp, expected)

    def assertFunc(self, path, expected):
        self.assertEqual(self.func(path), expected)

    def test_none_on_missing(self):
        fp = pjoin(self.dir, 'nonexistant')
        self.assertRaises(EnvironmentError, self.func, fp)
        self.assertEqual(self.func(fp, True), None)
        data = self.test_cases[0]
        open(fp, 'wb').write(self.convert_data('dar', 'ascii'))
        self.assertEqual(self.func(fp, True),
            self.none_on_missing_ret_data)


class cpy_readfile_Test(native_readfile_Test):
    cpy_setup_class(locals(), 'readfile')


class native_readfile_ascii_Test(native_readfile_Test):
    func = staticmethod(osutils.native_readfile_ascii)


class cpy_readfile_ascii_Test(native_readfile_ascii_Test):
    cpy_setup_class(locals(), 'readfile_ascii')


class native_readfile_ascii_strict_Test(native_readfile_ascii_Test):
    func = staticmethod(osutils.native_readfile_ascii_strict)
    test_cases = native_readfile_ascii_Test.test_cases + [
        (u'\xf2', 'latin', (ValueError, UnicodeDecodeError)),
        (u'\ua000', 'utf8', UnicodeDecodeError),
        ]

class cpy_readfile_ascii_strict_Test(native_readfile_ascii_strict_Test):
    cpy_setup_class(locals(), 'readfile_ascii_strict')


class native_readfile_utf8_Test(native_readfile_Test):
    func = staticmethod(osutils.native_readfile_utf8)
    default_encoding = 'utf8'

class cpy_readfile_utf8_Test(native_readfile_utf8_Test):
    cpy_setup_class(locals(), 'readfile_utf8')

class native_readfile_utf8_strict_Test(native_readfile_Test):
    func = staticmethod(osutils.native_readfile_utf8_strict)
    default_encoding = 'utf8'
    test_cases = native_readfile_ascii_Test.test_cases + [
        u'\ua000fa',
        ]

class cpy_readfile_utf8_Test(native_readfile_utf8_Test):
    cpy_setup_class(locals(), 'readfile_utf8_strict')

class native_readfile_bytes_Test(native_readfile_Test):
    func = staticmethod(osutils.native_readfile_bytes)
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
            self.assertEqual(tuple(self.func(path)),
                expected)
            return
        data = tuple(self.func(path))
        if 'strict' not in self.encoding_mode and not compatibility.is_py3k:
            data = tuple(x.decode() for x in data)
        self.assertEqual(data, expected)

    def test_none_on_missing(self):
        fp = pjoin(self.dir, 'nonexistant')
        self.assertRaises(EnvironmentError, self.func, fp)
        self.assertEqual(tuple(self.func(fp, False, True)), ())
        data = self.test_cases[0]
        open(fp, 'wb').write(self.convert_data('dar', 'ascii'))
        self.assertEqual(tuple(self.func(fp, True)),
            (self.none_on_missing_ret_data,))

    def test_strip_whitespace(self):
        fp = pjoin(self.dir, 'data')

        open(fp, 'wb').write(self.convert_data(' dar1 \ndar2 \n dar3\n',
            'ascii'))
        results = tuple(self.func(fp, True))
        expected = ('dar1', 'dar2', 'dar3')
        if self.encoding_mode == 'bytes' and compatibility.is_py3k:
            expected = tuple(x.encode("ascii") for x in expected)
        self.assertEqual(results, expected)

        # this time without the trailing newline...
        open(fp, 'wb').write(self.convert_data(' dar1 \ndar2 \n dar3',
            'ascii'))
        results = tuple(self.func(fp, True))
        self.assertEqual(results, expected)


        # test a couple of edgecases; underly c extension has gotten these
        # wrong before.
        open(fp, 'wb').write(self.convert_data('0', 'ascii'))
        results = tuple(self.func(fp, True))
        expected = ('0',)
        if self.encoding_mode == 'bytes' and compatibility.is_py3k:
            expected = tuple(x.encode("ascii") for x in expected)
        self.assertEqual(results, expected)

        open(fp, 'wb').write(self.convert_data('0\n', 'ascii'))
        results = tuple(self.func(fp, True))
        expected = ('0',)
        if self.encoding_mode == 'bytes' and compatibility.is_py3k:
            expected = tuple(x.encode("ascii") for x in expected)
        self.assertEqual(results, expected)

        open(fp, 'wb').write(self.convert_data('0 ', 'ascii'))
        results = tuple(self.func(fp, True))
        expected = ('0',)
        if self.encoding_mode == 'bytes' and compatibility.is_py3k:
            expected = tuple(x.encode("ascii") for x in expected)
        self.assertEqual(results, expected)


def mk_readlines_test(scope, mode):
    func_name = 'readlines_%s' % mode
    base = globals()['native_readfile_%s_Test' % mode]

    class kls(readlines_mixin, base):
        func = staticmethod(getattr(osutils, func_name))
        encoding_mode = mode

    kls.__name__ = "%s_Test" % func_name
    scope["%s_Test" % func_name] = kls

for case in ("ascii", "ascii_strict", "bytes",
    "utf8"):

    name = 'readlines_%s' % case
    mk_readlines_test(locals(), case)


class TestAccess(TempDirMixin):

    if osutils.access is os.access:
        skip = "os.access is used, no need to test"
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
        open(path, 'w')
        f(path)
        self.assertFalse(os.path.exists(path))
        # and once more for good measure...
        f(path)

cpy_readdir_loaded_Test = mk_cpy_loadable_testcase("snakeoil.osutils._readdir",
    "snakeoil.osutils", "listdir", "listdir")
cpy_posix_loaded_Test = mk_cpy_loadable_testcase("snakeoil.osutils._posix",
    "snakeoil.osutils", "normpath", "normpath")
