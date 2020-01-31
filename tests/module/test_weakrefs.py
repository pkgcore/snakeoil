from weakref import WeakValueDictionary

import pytest

from snakeoil.weakrefs import WeakValCache


class RefObj:
    pass


@pytest.mark.skipif(
    WeakValueDictionary is WeakValCache,
    reason="WeakValCache is weakref.WeakValueDictionary; indicates "
           "snakeoil._caching isn't compiled")
class TestWeakValCache:

    def setup_method(self, method):
        self.o = RefObj()
        self.w = WeakValCache()

    def test_setitem(self):
        s = "asdf"
        self.w[s] = self.o
        self.w["fds"] = self.o
        self.w[s] = self.o

    def test_getitem(self):
        s = "asdf"
        self.w[s] = self.o
        assert self.w[s] is self.o

    def test_expiring(self):
        s = "asdf"
        self.w[s] = self.o
        assert self.w[s]
        del self.o
        with pytest.raises(KeyError):
            self.w.__getitem__(s)

    def test_get(self):
        s = "asdf"
        with pytest.raises(KeyError):
            self.w.__getitem__(s)
        self.w[s] = self.o
        assert self.w.get(s) is self.o

    def test_keys(self):
        assert list(self.w.keys()) == []
        self.w['a'] = self.o
        self.w['b'] = self.o
        self.w['c'] = self.o
        assert sorted(self.w.keys()) == ['a', 'b', 'c']
        del self.o
        assert self.w.keys() == []

    def test_values(self):
        assert list(self.w.values()) == []
        self.w['a'] = self.o
        self.w['b'] = self.o
        self.w['c'] = self.o
        assert len(iter(self.w.values())) == 3
        del self.o
        assert self.w.values() == []

    def test_items(self):
        assert list(self.w.items()) == []
        self.w['a'] = self.o
        self.w['b'] = self.o
        self.w['c'] = self.o
        assert len(iter(self.w.items())) == 3
        del self.o
        assert self.w.items() == []
