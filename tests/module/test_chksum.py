import pytest

from snakeoil import chksum


class Test_funcs:

    def setup_method(self, method):
        chksum.__inited__ = False
        chksum.chksum_types.clear()
        self._saved_init = chksum.init
        self._inited_count = 0
        def f():
            self._inited_count += 1
            chksum.__inited__ = True
        chksum.init = f

    # ensure we aren't mangling chksum state for other tests.
    def teardown_method(self, method):
        chksum.__inited__ = False
        chksum.chksum_types.clear()
        chksum.init = self._saved_init

    def test_get_handlers(self):
        expected = {"x": 1, "y": 2}
        chksum.chksum_types.update(expected)
        assert expected == chksum.get_handlers()
        assert self._inited_count == 1
        assert expected == chksum.get_handlers(None)
        assert {"x": 1} == chksum.get_handlers(["x"])
        assert expected == chksum.get_handlers(["x", "y"])
        assert self._inited_count == 1

    def test_get_handler(self):
        with pytest.raises(chksum.MissingChksumHandler):
            chksum.get_handler("x")
        assert self._inited_count == 1
        chksum.chksum_types["x"] = 1
        with pytest.raises(chksum.MissingChksumHandler):
            chksum.get_handler("y")
        chksum.chksum_types["y"] = 2
        assert chksum.get_handler("x") == 1
        assert chksum.get_handler("y") == 2
        assert self._inited_count == 1

