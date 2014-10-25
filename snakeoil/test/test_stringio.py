# Copyright: 2010 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD 3 clause


from snakeoil.test import TestCase
from snakeoil import stringio

class base(object):

    encoding = None
    kls = None

    def convert_data(self, data):
        if self.encoding is None:
            return data
        return data.encode(self.encoding)

    def unconvert_data(self, data):
        if self.encoding is None:
            return data
        return data.decode(self.encoding)


class readonly_mixin(base):

    def test_nonwritable(self):
        convert = self.convert_data
        obj = self.kls(convert("adsf"))
        self.assertRaises(TypeError, obj.write,
                          convert("bow ties"))
        self.assertRaises(TypeError, obj.writelines,
                          convert("are cool"),
                          convert(" so says the doctor"))
        self.assertRaises(TypeError, obj.truncate)


class writable_mixin(base):

    def test_writable(self):
        convert = self.convert_data
        obj = self.kls(convert("bow ties"))
        self.assertEqual(obj.getvalue(), convert("bow ties"))
        # assert we start at 0
        self.assertEqual(obj.tell(), 0)
        obj.write(convert("are cool"))
        self.assertEqual(obj.getvalue(), convert("are cool"))
        obj.seek(0)
        obj.truncate(0)
        self.assertEqual(obj.getvalue(), convert(""))


class Test_text_readonly(readonly_mixin, TestCase):
    kls = stringio.text_readonly

class Test_text_writable(writable_mixin, TestCase):
    kls = stringio.text_writable

class Bytes_text_readonly(readonly_mixin, TestCase):
    kls = stringio.bytes_readonly
    encoding = 'utf8'

class Bytes_text_writable(writable_mixin, TestCase):
    kls = stringio.bytes_writable
    encoding = 'utf8'

