import pytest

from snakeoil import obj

# sorry, but the name is good, just too long for these tests
make_DI = obj.DelayedInstantiation
make_DIkls = obj.DelayedInstantiation_kls


class TestDelayedInstantiation:

    def test_simple(self):
        t = tuple([1, 2, 3])
        o = make_DI(tuple, lambda: t)
        assert str(t) == str(o)
        assert repr(t) == repr(o)
        assert hash(t) == hash(o)
        assert t <= o
        assert t == o
        assert t >= o

    def test_descriptor_awareness(self):
        def assertKls(cls, ignores=(),
                      default_ignores=("__new__", "__init__", "__init_subclass__",
                                       "__getattribute__", "__class__",
                                       "__getnewargs__", "__doc__",
                                       "__class_getitem__")):
            required = set(x for x in dir(cls)
                           if x.startswith("__") and x.endswith("__"))
            missing = required.difference(obj.kls_descriptors)
            missing.difference_update(obj.base_kls_descriptors)
            missing.difference_update(default_ignores)
            missing.difference_update(ignores)
            assert not missing, ("object %r potentially has unsupported special "
                                 "attributes: %s" % (cls, ', '.join(missing)))

        assertKls(object)
        assertKls(1)
        assertKls(object())
        assertKls(list)
        assertKls({})
        assertKls(set())

    def test_BaseDelayedObject(self):
        # assert that all methods/descriptors of object
        # are covered via the base.
        o = set(dir(object)).difference("__%s__" % x for x in [
            "class", "getattribute", "new", "init", "init_subclass", "doc"])
        diff = o.difference(obj.base_kls_descriptors)
        assert not diff, ("base delayed instantiation class should cover all of object, but "
                          "%r was spotted" % (",".join(sorted(diff)),))
        assert obj.DelayedInstantiation_kls(int, "1") + 2 == 3


    def test_klass_choice_optimization(self):
        """ensure that BaseDelayedObject is used whenever possible"""

        # note object is an odd one- it actually has a __doc__, thus
        # it must always be a custom
        o = make_DI(object, object)
        assert object.__getattribute__(o, '__class__') is not obj.BaseDelayedObject
        class foon:
            pass
        o = make_DI(foon, foon)
        cls = object.__getattribute__(o, '__class__')
        assert cls is obj.BaseDelayedObject

        # now ensure we always get the same kls back for derivatives
        class foon:
            def __bool__(self):
                return True

        o = make_DI(foon, foon)
        cls = object.__getattribute__(o, '__class__')
        assert cls is not obj.BaseDelayedObject
        o = make_DI(foon, foon)
        cls2 = object.__getattribute__(o, '__class__')
        assert cls is cls2

    def test__class__(self):
        l = []
        def f():
            l.append(False)
            return True
        o = make_DI(bool, f)
        assert isinstance(o, bool)
        assert not l, "accessing __class__ shouldn't trigger instantiation"

    def test__doc__(self):
        l = []
        def f():
            l.append(True)
            return foon()
        class foon:
            __doc__ = "monkey"

        o = make_DI(foon, f)
        assert o.__doc__ == 'monkey'
        assert not l, (
            "in accessing __doc__, the instance was generated- "
            "this is a class level attribute, thus shouldn't "
            "trigger instantiation")


class TestPopattr:

    class Object:
        pass

    def setup_method(self, method):
        self.o = self.Object()
        self.o.test = 1

    def test_no_attrs(self):
        # object without any attrs
        with pytest.raises(AttributeError):
            obj.popattr(object(), 'nonexistent')

    def test_nonexistent_attr(self):
        # object with attr trying to get nonexistent attr
        with pytest.raises(AttributeError):
            obj.popattr(self.o, 'nonexistent')

    def test_fallback(self):
        # object with attr trying to get nonexistent attr using fallback
        value = obj.popattr(self.o, 'nonexistent', 2)
        assert value == 2

    def test_removed_attr(self):
        value = obj.popattr(self.o, 'test')
        assert value == 1
        # verify that attr was removed from the object
        with pytest.raises(AttributeError):
            obj.popattr(self.o, 'test')
