# TODO: deprecated, remove in 0.9.0

import pytest

from snakeoil import stringio


class readonly_mixin:

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

    def test_nonwritable(self):
        convert = self.convert_data
        obj = self.kls(convert("adsf"))
        with pytest.raises(TypeError):
            obj.write(convert("bow ties"))
        with pytest.raises(TypeError):
            obj.writelines(convert("are cool"), convert(" so says the doctor"))
        with pytest.raises(TypeError):
            obj.truncate()


class Test_text_readonly(readonly_mixin):
    kls = stringio.text_readonly

class Test_bytes_readonly(readonly_mixin ):
    kls = stringio.bytes_readonly
    encoding = 'utf8'
