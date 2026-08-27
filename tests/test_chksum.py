import pickle

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


class TestLazilyHashedPath:
    def test_pickling(self):
        obj = chksum.LazilyHashedPath("/dev/null", size=0, md5="deadbeef")
        new = pickle.loads(pickle.dumps(obj))
        assert (new.path, new.size, new.md5) == ("/dev/null", 0, "deadbeef")

    def test_clear(self, tmp_path):
        path = tmp_path / "file"
        path.write_text("Hello world")
        obj = chksum.LazilyHashedPath(str(path))

        assert obj.md5
        assert "md5" in vars(obj)
        obj.clear()
        assert "md5" not in vars(obj)
        assert "path" in vars(obj)

        # clearing must not compute anything, so it stays usable for a path
        # that no longer exists
        path.unlink()
        obj.clear()
