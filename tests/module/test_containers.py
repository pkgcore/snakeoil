from itertools import chain

import pytest

from snakeoil import containers


class TestInvertedContains:

    def setup_method(self, method):
        self.set = containers.InvertedContains(range(12))

    def test_basic(self):
        assert 7 not in self.set
        assert -7 in self.set
        with pytest.raises(TypeError):
            iter(self.set)


class BasicSet(containers.SetMixin):
    __slots__ = ('_data',)

    def __init__(self, data):
        self._data = set(data)

    def __iter__(self):
        return iter(self._data)

    def __contains__(self, other):
        return other in self._data

    #def __str__(self):
    #    return 'BasicSet([%s])' % ', '.join((str(x) for x in self._data))

    def __eq__(self, other):
        if isinstance(other, BasicSet):
            return self._data == other._data
        elif isinstance(other, (set, frozenset)):
            return self._data == other
        return False

    def __ne__(self, other):
        return not self == other


class TestSetMethods:

    def test_and(self):
        c = BasicSet(range(100))
        s = set(range(25, 75))
        r = BasicSet(range(25, 75))
        assert c & s == r
        assert s & c == r._data

    def test_xor(self):
        c = BasicSet(range(100))
        s = set(range(25, 75))
        r = BasicSet(chain(range(25), range(75, 100)))
        assert c ^ s == r
        assert s ^ c == r._data

    def test_or(self):
        c = BasicSet(range(50))
        s = set(range(50, 100))
        r = BasicSet(range(100))
        assert c | s == r
        assert s | c == r._data

    def test_add(self):
        c = BasicSet(range(50))
        s = set(range(50, 100))
        r = BasicSet(range(100))
        assert c + s == r
        assert s + c == r._data

    def test_sub(self):
        c = BasicSet(range(100))
        s = set(range(50, 150))
        r1 = BasicSet(range(50))
        r2 = set(range(100, 150))
        assert c - s == r1
        assert s - c == r2

class TestLimitedChangeSet:

    def setup_method(self, method):
        self.set = containers.LimitedChangeSet(range(12))

    def test_validator(self):
        def f(val):
            assert isinstance(val, int)
            return val
        self.set = containers.LimitedChangeSet(range(12), key_validator=f)
        self.set.add(13)
        self.set.add(14)
        self.set.remove(11)
        assert 5 in self.set
        with pytest.raises(AssertionError):
            self.set.add('2')
        with pytest.raises(AssertionError):
            self.set.remove('2')
        with pytest.raises(AssertionError):
            self.set.__contains__('2')

    def test_basic(self, changes=0):
        # this should be a no-op
        self.set.rollback(changes)
        # and this is invalid
        with pytest.raises(TypeError):
            self.set.rollback(changes + 1)
        assert 0 in self.set
        assert 12 not in self.set
        assert 12 == len(self.set)
        assert sorted(list(self.set)) == list(range(12))
        assert changes == self.set.changes_count()
        with pytest.raises(TypeError):
            self.set.rollback(-1)

    def test_dummy_commit(self):
        # this should be a no-op
        self.set.commit()
        # so this should should run just as before
        self.test_basic()

    def test_adding(self):
        self.set.add(13)
        assert 13 in self.set
        assert 13 == len(self.set)
        assert sorted(list(self.set)) == list(range(12)) + [13]
        assert 1 == self.set.changes_count()
        self.set.add(13)
        with pytest.raises(containers.Unchangable):
            self.set.remove(13)

    def test_add_rollback(self):
        self.set.add(13)
        self.set.rollback(0)
        # this should run just as before
        self.test_basic()

    def test_add_commit_remove_commit(self):
        self.set.add(13)
        self.set.commit()
        # should look like right before commit
        assert 13 == len(self.set)
        assert sorted(list(self.set)) == list(range(12)) + [13]
        assert 0 == self.set.changes_count()
        # and remove...
        self.set.remove(13)
        # should be back to basic, but with 1 change
        self.test_basic(1)
        self.set.commit()
        self.test_basic()

    def test_removing(self):
        self.set.remove(0)
        assert 0 not in self.set
        assert 11 == len(self.set)
        assert sorted(list(self.set)) == list(range(1, 12))
        assert 1 == self.set.changes_count()
        with pytest.raises(containers.Unchangable):
            self.set.add(0)
        with pytest.raises(KeyError):
            self.set.remove(0)

    def test_remove_rollback(self):
        self.set.remove(0)
        self.set.rollback(0)
        self.test_basic()

    def test_remove_commit_add_commit(self):
        self.set.remove(0)
        self.set.commit()
        assert 0 not in self.set
        assert 11 == len(self.set)
        assert sorted(list(self.set)) == list(range(1, 12))
        assert 0 == self.set.changes_count()
        self.set.add(0)
        self.test_basic(1)
        self.set.commit()
        self.test_basic()

    def test_longer_transaction(self):
        self.set.add(12)
        self.set.remove(7)
        self.set.rollback(1)
        self.set.add(-1)
        self.set.commit()
        assert sorted(list(self.set)) == list(range(-1, 13))

    def test_str(self):
        assert str(containers.LimitedChangeSet([7])) == 'LimitedChangeSet([7])'

    def test__eq__(self):
        c = containers.LimitedChangeSet(range(99))
        c.add(99)
        assert c == containers.LimitedChangeSet(range(100))
        assert containers.LimitedChangeSet(range(100)) == set(range(100))
        assert containers.LimitedChangeSet([]) != object()


class TestLimitedChangeSetWithBlacklist:

    def setup_method(self, method):
        self.set = containers.LimitedChangeSet(range(12), [3, 13])

    def test_basic(self):
        assert 0 in self.set
        assert 12 not in self.set
        assert 12 == len(self.set)
        assert sorted(list(self.set)) == list(range(12))
        assert 0 == self.set.changes_count()
        with pytest.raises(TypeError):
            self.set.rollback(-1)

    def test_adding_blacklisted(self):
        with pytest.raises(containers.Unchangable):
            self.set.add(13)

    def test_removing_blacklisted(self):
        with pytest.raises(containers.Unchangable):
            self.set.remove(3)


class TestProtectedSet:

    def setup_method(self, method):
        self.set = containers.ProtectedSet(set(range(12)))

    def test_contains(self):
        assert 0 in self.set
        assert 15 not in self.set
        self.set.add(15)
        assert 15 in self.set

    def test_iter(self):
        assert list(range(12)) == sorted(self.set)
        self.set.add(5)
        assert list(range(12)) == sorted(self.set)
        self.set.add(12)
        assert list(range(13)) == sorted(self.set)

    def test_len(self):
        assert 12 == len(self.set)
        self.set.add(5)
        self.set.add(13)
        assert 13 == len(self.set)


class TestRefCountingSet:

    kls = containers.RefCountingSet

    def test_it(self):
        c = self.kls((1, 2))
        assert 1 in c
        assert 2 in c
        c.remove(1)
        assert 1 not in c
        with pytest.raises(KeyError):
            c.remove(1)
        c.add(2)
        assert 2 in c
        c.remove(2)
        assert 2 in c
        c.remove(2)
        assert 2 not in c
        c.add(3)
        assert 3 in c
        c.remove(3)
        assert 3 not in c

        c.discard(4)
        c.discard(5)
        c.discard(4)
        c.add(4)
        c.add(4)
        assert 4 in c
        c.discard(4)
        assert 4 in c
        c.discard(4)
        assert 4 not in c

    def test_init(self):
        assert self.kls(range(5))[4] == 1
        c = self.kls([1, 2, 3, 1])
        assert c[2] == 1
        assert c[1] == 2
