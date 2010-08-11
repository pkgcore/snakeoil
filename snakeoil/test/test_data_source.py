# Copyright: 2006 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD

import os
from snakeoil import data_source
from snakeoil.test import TestCase, mixins
from snakeoil import compatibility
from snakeoil import stringio, currying


class TestDataSource(TestCase):

    supports_mutable = False

    def get_obj(self, mutable=False):
        return data_source.data_source("foonani", mutable=mutable)

    def test_get_path(self):
        obj = self.get_obj()
        self.assertIdentical(obj.get_path, None)

    def _test_fileobj_ro(self, attr, converter=str):
        obj = self.get_obj()
        # ensure that requesting mutable from an immutable isn't allowed
        self.assertRaises(TypeError, getattr(obj, attr), True)
        handle = getattr(obj, attr)()
        self.assertEqual(handle.read(), converter("foonani"))
        self.assertRaises(handle.exceptions, handle.write,
            converter("monkey"))

    def _test_fileobj_wr(self, attr, converter=str):

        obj = self.get_obj(True)
        handle_f = getattr(obj, attr)
        self.assertEqual(handle_f().read(),
            converter("foonani"))
        f = handle_f(True)
        f.write(converter("dar"))
        f.close()
        self.assertEqual(handle_f(True).read(),
            converter("darnani"))

    def test_text_fileobj(self):
        self._test_fileobj_ro("text_fileobj", str)
        if self.supports_mutable:
            self._test_fileobj_wr("text_fileobj", str)

    def test_bytes_fileobj(self):
        self._test_fileobj_ro("bytes_fileobj",
            compatibility.force_bytes)
        if self.supports_mutable:
            self._test_fileobj_wr("bytes_fileobj",
                compatibility.force_bytes)

    def test_get_textfileobj(self):
        # just validate we get back an obj...
        # not quite blackbox, but we know we test the functionality above-
        # thus no point in repeating it just for an aliasing of the method name
        self.get_obj().get_text_fileobj()

    def test_get_textfileobj(self):
        # just validate we get back an obj...
        # not quite blackbox, but we know we test the functionality above-
        # thus no point in repeating it just for an aliasing of the method name
        self.get_obj().get_bytes_fileobj()


class TestLocalSource(mixins.TempDirMixin, TestDataSource):

    def get_obj(self, mutable=False, data="foonani"):
        self.fp = os.path.join(self.dir, "localsource.test")
        f = None
        if compatibility.is_py3k:
            if isinstance(data, bytes):
                f = open(self.fp, 'wb')
        if f is None:
            f = open(self.fp, "w")
        f.write(data)
        return data_source.local_source(self.fp, mutable=mutable)

    def test_get_path(self):
        self.assertEqual(self.get_obj().get_path(), self.fp)

    def test_get_bytes_fileobj(self):
        data = u"foonani\xf2".encode("utf8")
        obj = self.get_obj(data=data)
        # this will blow up if tries to ascii decode it.
        self.assertEqual(obj.get_bytes_fileobj().read(), data)


class Test_invokable_data_source(TestDataSource):

    supports_mutable = False

    def get_obj(self, mutable=False, data="foonani"):
        if isinstance(data, basestring):
            data = data.encode("utf8")
        return data_source.invokable_data_source(
            currying.partial(self._get_data, data))

    @staticmethod
    def _get_data(data, is_text=False):
        if is_text:
            data = data.decode("utf8")
            return data_source.text_ro_StringIO(data)
        return data_source.bytes_ro_StringIO(data)


class Test_invokable_data_source_wrapper_text(Test_invokable_data_source):

    supports_mutable = False
    text_mode = True

    def get_obj(self, mutable=False, data="foonani"):
        return data_source.invokable_data_source.wrap_function(
            currying.partial(self._get_data, data),
            self.text_mode)

    def _get_data(self, data='foonani'):
        if isinstance(data, basestring):
            if not self.text_mode:
                return data.encode("utf8")
        elif self.text_mode:
            return data.encode("utf8")
        return data


class Test_invokable_data_source_wrapper_bytes(Test_invokable_data_source_wrapper_text):

    text_mode = False


class Test_transfer_data(TestDataSource):

    func = staticmethod(data_source.transfer_data)

    def assertTransfer(self, reader, writer):
        r_position = reader.tell()
        w_position = writer.tell()
        self.func(reader, writer)

        r_size = reader.tell() - r_position
        # make sure no data is remaining
        self.assertFalse(reader.read())
        self.assertEqual(writer.tell() - w_position, r_size)
        writer.seek(w_position, 0)
        reader.seek(r_position)
        data = reader.read()
        self.assertLen(data, r_size)
        self.assertEqual(data, writer.read())

    def _mk_data(self, size=(100000)):
        return ''.join("%s" % (x % 10)
            for x in xrange(size))

    def test_it(self):
        data = self._mk_data()
        reader = stringio.text_readonly(data)
        writer = stringio.text_writable(data)
        self.assertTransfer(reader, writer)
        writer.seek(5, 0)
        reader.seek(0)
        self.assertTransfer(reader, writer)
        writer.seek(0)
        self.assertEqual(writer.getvalue()[5:],
            data)
        self.assertEqual(writer.getvalue()[:5],
            data[:5])
