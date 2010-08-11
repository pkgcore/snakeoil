# Copyright: 2005 Marien Zwart <marienz@gentoo.org>
# Copyright: 2010 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2


import os
from StringIO import StringIO
from snakeoil import compatibility
from snakeoil.test.mixins import mk_named_tempfile
from snakeoil.test import TestCase

pjoin = os.path.join

from snakeoil.fileutils import (
    read_dict, AtomicWriteFile, ParseError)
from snakeoil.test.mixins import TempDirMixin


class TestReadBashConfig(TestCase):

    def test_read_dict(self):
        self.assertEqual(
            read_dict(StringIO(
                    '\n'
                    '# hi I am a comment\n'
                    'foo1=bar\n'
                    'foo2="bar"\n'
                    'foo3=\'bar"\n'
                    )),
            {'foo1': 'bar',
             'foo2': 'bar',
             'foo3': '\'bar"',
             })
        self.assertEqual(
            read_dict(['foo=bar'], source_isiter=True), {'foo': 'bar'})
        self.assertRaises(
            ParseError, read_dict, ['invalid'], source_isiter=True)
        self.assertEqual(
            read_dict(StringIO("foo bar\nfoo2  bar\nfoo3\tbar\n"),
                splitter=None),
            {}.fromkeys(('foo', 'foo2', 'foo3'), 'bar'))


class TestAtomicWriteFile(TempDirMixin):

    kls = AtomicWriteFile

    def test_normal_ops(self):
        fp = pjoin(self.dir, "target")
        open(fp, "w").write("me")
        af = self.kls(fp)
        af.write("dar")
        self.assertEqual(open(fp, "r").read(), "me")
        af.close()
        self.assertEqual(open(fp, "r").read(), "dar")

    def test_perms(self):
        fp = pjoin(self.dir, 'target')
        orig_um = os.umask(0777)
        try:
            af = self.kls(fp, perms=0644)
            af.write("dar")
            af.close()
        finally:
            exiting_umask = os.umask(orig_um)
        self.assertEqual(exiting_umask, 0777)
        self.assertEqual(os.stat(fp).st_mode & 04777, 0644)

    def test_del(self):
        fp = pjoin(self.dir, "target")
        open(fp, "w").write("me")
        self.assertEqual(open(fp, "r").read(), "me")
        af = self.kls(fp)
        af.write("dar")
        del af
        self.assertEqual(open(fp, "r").read(), "me")
        self.assertEqual(len(os.listdir(self.dir)), 1)

    def test_close(self):
        # verify that we handle multiple closes; no exception is good.
        af = self.kls(pjoin(self.dir, "target"))
        af.close()
        af.close()

    def test_discard(self):
        fp = pjoin(self.dir, "target")
        open(fp, "w").write("me")
        self.assertEqual(open(fp, "r").read(), "me")
        af = self.kls(fp)
        af.write("dar")
        af.discard()
        self.assertFalse(os.path.exists(af._temp_fp))
        af.close()
        self.assertEqual(open(fp, "r").read(), "me")

        # finally validate that it handles multiple discards properly.
        af = self.kls(fp)
        af.write("dar")
        af.discard()
        af.discard()
        af.close()
