import operator
from itertools import chain

import pytest

from snakeoil.iterables import caching_iter, expandable_chain, iter_sort, partition


class TestPartition:
    def test_empty(self):
        a, b = partition(())
        assert list(a) == []
        assert list(b) == []

    def test_split(self):
        a, b = partition(range(10))
        assert list(a) == [0]
        assert list(b) == list(range(1, 10))

        a, b = partition(range(10), lambda x: x >= 5)
        assert list(a) == [0, 1, 2, 3, 4]
        assert list(b) == [5, 6, 7, 8, 9]


class TestExpandableChain:
    def test_normal_function(self):
        i = [iter(range(100)) for x in range(3)]
        e = expandable_chain()
        e.extend(i)
        assert list(e) == list(range(100)) * 3
        for x in i + [e]:
            pytest.raises(StopIteration, x.__next__)

    def test_extend(self):
        e = expandable_chain()
        e.extend(range(100) for i in (1, 2))
        assert list(e) == list(range(100)) * 2
        with pytest.raises(StopIteration):
            e.extend([[]])

    def test_extendleft(self):
        e = expandable_chain(range(20, 30))
        e.extendleft([range(10, 20), range(10)])
        assert list(e) == list(range(30))
        with pytest.raises(StopIteration):
            e.extendleft([[]])

    def test_append(self):
        e = expandable_chain()
        e.append(range(100))
        assert list(e) == list(range(100))
        with pytest.raises(StopIteration):
            e.append([])

    def test_appendleft(self):
        e = expandable_chain(range(10, 20))
        e.appendleft(range(10))
        assert list(e) == list(range(20))
        with pytest.raises(StopIteration):
            e.appendleft([])


class TestCachingIter:
    def test_iter_consumption(self):
        i = iter(range(100))
        c = caching_iter(i)
        i2 = iter(c)
        for _ in range(20):
            next(i2)
        assert next(i) == 20
        # note we consumed one ourselves
        assert c[20] == 21
        list(c)
        pytest.raises(StopIteration, i.__next__)
        assert list(c) == list(range(20)) + list(range(21, 100))

    def test_init(self):
        assert caching_iter(list(range(100)))[0] == 0

    def test_full_consumption(self):
        i = iter(range(100))
        c = caching_iter(i)
        assert list(c) == list(range(100))
        # do it twice, to verify it returns properly
        assert list(c) == list(range(100))

    def test_len(self):
        assert 100 == len(caching_iter(range(100)))

    def test_hash(self):
        assert hash(caching_iter(range(100))) == hash(tuple(range(100)))

    def test_bool(self):
        c = caching_iter(range(100))
        assert bool(c)
        # repeat to check if it works when cached.
        assert bool(c)
        assert not bool(caching_iter(iter([])))

    def test_cmp(self):
        assert tuple(caching_iter(range(100))) == tuple(range(100))
        assert tuple(caching_iter(range(90))) != tuple(range(100))
        assert tuple(caching_iter(range(100))) > tuple(range(90))
        assert not tuple(caching_iter(range(90))) > tuple(range(100))
        assert tuple(caching_iter(range(100))) >= tuple(range(100))
        assert tuple(caching_iter(range(90))) < tuple(range(100))
        assert not tuple(caching_iter(range(100))) < tuple(range(90))
        assert tuple(caching_iter(range(90))) <= tuple(range(100))

    def test_sorter(self):
        assert tuple(caching_iter(range(100, 0, -1), sorted)) == tuple(range(1, 101))
        c = caching_iter(range(100, 0, -1), sorted)
        assert c
        assert tuple(iter(c)) == tuple(range(1, 101))
        c = caching_iter(range(50, 0, -1), sorted)
        assert c[10] == 11
        assert tuple(iter(c)) == tuple(range(1, 51))

    def test_getitem(self):
        c = caching_iter(range(20))
        assert c[-1] == 19
        with pytest.raises(IndexError):
            operator.getitem(c, -21)
        with pytest.raises(IndexError):
            operator.getitem(c, 21)

    def test_edgecase(self):
        c = caching_iter(range(5))
        assert c[0] == 0
        # do an off by one access- this actually has broke before
        assert c[2] == 2
        assert c[1] == 1
        assert list(c) == list(range(5))

    def test_setitem(self):
        with pytest.raises(TypeError):
            operator.setitem(caching_iter(range(10)), 3, 4)

    def test_str(self):
        # Just make sure this works at all.
        assert str(caching_iter(range(10)))


class Test_iter_sort:
    def test_ordering(self):
        def f(l):
            return sorted(l, key=operator.itemgetter(0))

        result = list(iter_sort(f, *[iter(range(x, x + 10)) for x in (30, 20, 0, 10)]))
        expected = list(range(40))
        assert result == expected

    @pytest.mark.parametrize(
        "iterables",
        (
            pytest.param(([1, 2], [1, 3]), id="leading-element-ties"),
            pytest.param(([1, 1], [1, 1], [1]), id="everything-ties"),
            pytest.param(([1, 2, 3], [2, 3, 4], [3, 4, 5]), id="overlapping"),
            pytest.param(([], [2, 3], []), id="empties"),
            pytest.param(([3, 4],), id="single"),
            pytest.param((), id="none"),
        ),
    )
    def test_bare_sorted(self, iterables):
        # the sorter needn't pull the element out itself; iterables that tie on
        # it must not end up compared against each other.
        assert sorted(chain(*iterables)) == list(iter_sort(sorted, *iterables))

    def test_ties_keep_input_order(self):
        class tied:
            """every instance compares equal, so ordering falls to the iterable"""

            def __init__(self, name):
                self.name = name

            def __eq__(self, other):
                return isinstance(other, tied)

            def __lt__(self, other):
                return False

        left, right = tied("left"), tied("right")
        for order in ((left, right), (right, left)):
            result = iter_sort(sorted, *([x] for x in order))
            assert [x.name for x in order] == [x.name for x in result]
