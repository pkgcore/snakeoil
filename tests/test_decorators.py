import pytest

from snakeoil.decorators import coroutine


class TestCoroutineDecorator:
    def test_coroutine(self):
        @coroutine
        def count():
            i = 0
            while True:
                val = yield i
                i = val if val is not None else i + 1

        cr = count()

        # argument required
        with pytest.raises(TypeError):
            cr.send()

        assert cr.send(-1) == -1
        assert next(cr) == 0
        assert next(cr) == 1
        assert cr.send(10) == 10
        assert next(cr) == 11
