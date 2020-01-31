# TODO: deprecated, remove in 0.9.0

import pytest

from snakeoil import stringio


class base:

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
        with pytest.raises(TypeError):
            obj.write(convert("bow ties"))
        with pytest.raises(TypeError):
            obj.writelines(convert("are cool"), convert(" so says the doctor"))
        with pytest.raises(TypeError):
            obj.truncate()


class writable_mixin(base):

    def test_writable(self):
        convert = self.convert_data
        obj = self.kls(convert("bow ties"))
        assert obj.getvalue() == convert("bow ties")
        # assert we start at 0
        assert obj.tell() == 0
        obj.write(convert("are cool"))
        assert obj.getvalue() == convert("are cool")
        obj.seek(0)
        obj.truncate(0)
        assert obj.getvalue() == convert("")


class Test_text_readonly(readonly_mixin):
    kls = stringio.text_readonly

class Test_text_writable(writable_mixin):
    kls = stringio.text_writable

class Test_bytes_readonly(readonly_mixin ):
    kls = stringio.bytes_readonly
    encoding = 'utf8'

class Test_bytes_writable(writable_mixin ):
    kls = stringio.bytes_writable
    encoding = 'utf8'
