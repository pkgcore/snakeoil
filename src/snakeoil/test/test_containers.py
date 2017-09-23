# Copyright: 2005 Marien Zwart <marienz@gentoo.org>
# Copyright: 2010 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2


from itertools import chain

from snakeoil.test import TestCase
from snakeoil import containers


class InvertedContainsTest(TestCase):

    def setUp(self):
        self.set = containers.InvertedContains(range(12))

    def test_basic(self):
        self.assertFalse(7 in self.set)
        self.assertTrue(-7 in self.set)
        self.assertRaises(TypeError, iter, self.set)


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


class TestSetMethods(TestCase):
    def test_and(self):
        c = BasicSet(xrange(100))
        s = set(xrange(25, 75))
        r = BasicSet(xrange(25, 75))
        self.assertEqual(c & s, r)
        self.assertEqual(s & c, r._data)

    def test_xor(self):
        c = BasicSet(xrange(100))
        s = set(xrange(25, 75))
        r = BasicSet(chain(xrange(25), xrange(75, 100)))
        self.assertEqual(c ^ s, r)
        self.assertEqual(s ^ c, r._data)

    def test_or(self):
        c = BasicSet(xrange(50))
        s = set(xrange(50, 100))
        r = BasicSet(xrange(100))
        self.assertEqual(c | s, r)
        self.assertEqual(s | c, r._data)

    def test_add(self):
        c = BasicSet(xrange(50))
        s = set(xrange(50, 100))
        r = BasicSet(xrange(100))
        self.assertEqual(c + s, r)
        self.assertEqual(s + c, r._data)

    def test_sub(self):
        c = BasicSet(xrange(100))
        s = set(xrange(50, 150))
        r1 = BasicSet(xrange(50))
        r2 = set(xrange(100, 150))
        self.assertEqual(c - s, r1)
        self.assertEqual(s - c, r2)

class LimitedChangeSetTest(TestCase):

    def setUp(self):
        self.set = containers.LimitedChangeSet(range(12))

    def test_validator(self):
        def f(val):
            self.assertTrue(isinstance(val, int))
            return val
        self.set = containers.LimitedChangeSet(range(12), key_validator=f)
        self.set.add(13)
        self.set.add(14)
        self.set.remove(11)
        self.assertIn(5, self.set)
        self.assertRaises(AssertionError, self.set.add, '2')
        self.assertRaises(AssertionError, self.set.remove, '2')
        self.assertRaises(AssertionError, self.set.__contains__, '2')

    def test_basic(self, changes=0):
        # this should be a no-op
        self.set.rollback(changes)
        # and this is invalid
        self.assertRaises(TypeError, self.set.rollback, changes + 1)
        self.assertTrue(0 in self.set)
        self.assertFalse(12 in self.set)
        self.assertEqual(12, len(self.set))
        self.assertEqual(sorted(list(self.set)), list(range(12)))
        self.assertEqual(changes, self.set.changes_count())
        self.assertRaises(TypeError, self.set.rollback, -1)

    def test_dummy_commit(self):
        # this should be a no-op
        self.set.commit()
        # so this should should run just as before
        self.test_basic()

    def test_adding(self):
        self.set.add(13)
        self.assertTrue(13 in self.set)
        self.assertEqual(13, len(self.set))
        self.assertEqual(sorted(list(self.set)), list(range(12)) + [13])
        self.assertEqual(1, self.set.changes_count())
        self.set.add(13)
        self.assertRaises(containers.Unchangable, self.set.remove, 13)

    def test_add_rollback(self):
        self.set.add(13)
        self.set.rollback(0)
        # this should run just as before
        self.test_basic()

    def test_add_commit_remove_commit(self):
        self.set.add(13)
        self.set.commit()
        # should look like right before commit
        self.assertEqual(13, len(self.set))
        self.assertEqual(sorted(list(self.set)), list(range(12)) + [13])
        self.assertEqual(0, self.set.changes_count())
        # and remove...
        self.set.remove(13)
        # should be back to basic, but with 1 change
        self.test_basic(1)
        self.set.commit()
        self.test_basic()

    def test_removing(self):
        self.set.remove(0)
        self.assertFalse(0 in self.set)
        self.assertEqual(11, len(self.set))
        self.assertEqual(sorted(list(self.set)), list(range(1, 12)))
        self.assertEqual(1, self.set.changes_count())
        self.assertRaises(containers.Unchangable, self.set.add, 0)
        self.assertRaises(KeyError, self.set.remove, 0)

    def test_remove_rollback(self):
        self.set.remove(0)
        self.set.rollback(0)
        self.test_basic()

    def test_remove_commit_add_commit(self):
        self.set.remove(0)
        self.set.commit()
        self.assertFalse(0 in self.set)
        self.assertEqual(11, len(self.set))
        self.assertEqual(sorted(list(self.set)), range(1, 12))
        self.assertEqual(0, self.set.changes_count())
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
        self.assertEqual(sorted(list(self.set)), list(range(-1, 13)))

    def test_str(self):
        self.assertEqual(
            str(containers.LimitedChangeSet([7])), 'LimitedChangeSet([7])')

    def test__eq__(self):
        c = containers.LimitedChangeSet(xrange(99))
        c.add(99)
        self.assertEqual(c, containers.LimitedChangeSet(xrange(100)))
        self.assertEqual(containers.LimitedChangeSet(xrange(100)),
                         set(xrange(100)))
        self.assertNotEqual(containers.LimitedChangeSet([]), object())


class LimitedChangeSetWithBlacklistTest(TestCase):

    def setUp(self):
        self.set = containers.LimitedChangeSet(range(12), [3, 13])

    def test_basic(self):
        self.assertTrue(0 in self.set)
        self.assertFalse(12 in self.set)
        self.assertEqual(12, len(self.set))
        self.assertEqual(sorted(list(self.set)), list(range(12)))
        self.assertEqual(0, self.set.changes_count())
        self.assertRaises(TypeError, self.set.rollback, -1)

    def test_adding_blacklisted(self):
        self.assertRaises(containers.Unchangable, self.set.add, 13)

    def test_removing_blacklisted(self):
        self.assertRaises(containers.Unchangable, self.set.remove, 3)


class ProtectedSetTest(TestCase):

    def setUp(self):
        self.set = containers.ProtectedSet(set(range(12)))

    def test_contains(self):
        self.assertTrue(0 in self.set)
        self.assertFalse(15 in self.set)
        self.set.add(15)
        self.assertTrue(15 in self.set)

    def test_iter(self):
        self.assertEqual(range(12), sorted(self.set))
        self.set.add(5)
        self.assertEqual(range(12), sorted(self.set))
        self.set.add(12)
        self.assertEqual(range(13), sorted(self.set))

    def test_len(self):
        self.assertEqual(12, len(self.set))
        self.set.add(5)
        self.set.add(13)
        self.assertEqual(13, len(self.set))


class TestRefCountingSet(TestCase):

    kls = containers.RefCountingSet

    def test_it(self):
        c = self.kls((1, 2))
        self.assertIn(1, c)
        self.assertIn(2, c)
        c.remove(1)
        self.assertNotIn(1, c)
        self.assertRaises(KeyError, c.remove, 1)
        c.add(2)
        self.assertIn(2, c)
        c.remove(2)
        self.assertIn(2, c)
        c.remove(2)
        self.assertNotIn(2, c)
        c.add(3)
        self.assertIn(3, c)
        c.remove(3)
        self.assertNotIn(3, c)

        c.discard(4)
        c.discard(5)
        c.discard(4)
        c.add(4)
        c.add(4)
        self.assertIn(4, c)
        c.discard(4)
        self.assertIn(4, c)
        c.discard(4)
        self.assertNotIn(4, c)

    def test_init(self):
        self.assertEqual(self.kls(xrange(5))[4], 1)
        c = self.kls([1, 2, 3, 1])
        self.assertEqual(c[2], 1)
        self.assertEqual(c[1], 2)
