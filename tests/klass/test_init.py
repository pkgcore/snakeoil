import abc
import inspect
import re
import sys
from functools import partial
from time import time

import pytest

from snakeoil import klass
from snakeoil.klass.properties import _internal_jit_attr, _uncached_singleton

if sys.version_info >= (3, 13):
    from pytest import deprecated_call
else:
    import contextlib

    @contextlib.contextmanager
    def deprecated_call(*args, **kwargs):
        yield


class Test_GetAttrProxy:
    kls = staticmethod(klass.GetAttrProxy)

    def test_it(self):
        class foo1:
            def __init__(self, obj):
                self.obj = obj

            __getattr__ = self.kls("obj")

        class foo2:
            pass

        o2 = foo2()
        o = foo1(o2)
        with pytest.raises(AttributeError):
            getattr(o, "blah")
        assert o.obj == o2
        o2.foon = "dar"
        assert o.foon == "dar"
        o.foon = "foo"
        assert o.foon == "foo"

    def test_attrlist(self):
        def make_class(attr_list=None):
            class foo(metaclass=self.kls):
                if attr_list is not None:
                    locals()["__attr_comparison__"] = attr_list

        with pytest.raises(TypeError):
            make_class()
        with pytest.raises(TypeError):
            make_class(["foon"])
        with pytest.raises(TypeError):
            make_class([None])

    def test_instancemethod(self):
        class foo:
            bar = "baz"

        class Test:
            method = self.kls("test")
            test = foo()

        test = Test()
        assert test.method("bar") == foo.bar


class TestDirProxy:
    @staticmethod
    def noninternal_attrs(obj):
        return sorted(x for x in dir(obj) if not re.match(r"__\w+__", x))

    def test_combined(self):
        class foo1:
            def __init__(self, obj):
                self.obj = obj

            __dir__ = klass.DirProxy("obj")

        class foo2:
            def __init__(self):
                self.attr = "foo"

        o2 = foo2()
        o = foo1(o2)
        assert self.noninternal_attrs(o) == ["attr", "obj"]

    def test_empty(self):
        class foo1:
            def __init__(self, obj):
                self.obj = obj

            __dir__ = klass.DirProxy("obj")

        class foo2:
            pass

        o2 = foo2()
        o = foo1(o2)
        assert self.noninternal_attrs(o2) == []
        assert self.noninternal_attrs(o) == ["obj"]

    def test_slots(self):
        class foo1:
            __slots__ = ("obj",)

            def __init__(self, obj):
                self.obj = obj

            __dir__ = klass.DirProxy("obj")

        class foo2:
            __slots__ = ("attr",)

            def __init__(self):
                self.attr = "foo"

        o2 = foo2()
        o = foo1(o2)
        assert self.noninternal_attrs(o) == ["attr", "obj"]


class Test_contains:
    func = staticmethod(klass.contains)

    def test_it(self):
        class c(dict):
            __contains__ = self.func

        d = c({"1": 2})
        assert "1" in d
        assert 1 not in d


class Test_get:
    func = staticmethod(klass.get)

    def test_it(self):
        class c(dict):
            get = self.func

        d = c({"1": 2})
        assert d.get("1") == 2
        assert d.get("1", 3) == 2
        assert d.get(1) is None
        assert d.get(1, 3) == 3


class Test_chained_getter:
    @staticmethod
    def kls(*args, **kwargs):
        with deprecated_call():
            kwargs.setdefault("disable_inst_caching", True)
            return klass.chained_getter(*args, **kwargs)

    def test_hash(self):
        assert hash(self.kls("foon")) == hash("foon")
        assert hash(self.kls("foon.dar")) == hash("foon.dar")

    def test_caching(self):
        # since it caches, it'll only trigger the warning the *first* time, thus
        # invoke this ourselves directly
        with deprecated_call():
            assert klass.chained_getter(
                "asdf", disable_inst_caching=False
            ) is klass.chained_getter("asdf", disable_inst_caching=False)

    def test_eq(self):
        assert self.kls("asdf", disable_inst_caching=True) == self.kls(
            "asdf", disable_inst_caching=True
        )

        assert self.kls("asdf2", disable_inst_caching=True) != self.kls(
            "asdf", disable_inst_caching=True
        )

    def test_it(self):
        class maze:
            def __init__(self, kwargs):
                self.__data__ = kwargs

            def __getattr__(self, attr):
                return self.__data__.get(attr, self)

        d = {}
        m = maze(d)
        assert self.kls("foon")(m) == m
        d["foon"] = 1
        assert self.kls("foon")(m) == 1
        assert self.kls("dar.foon")(m) == 1
        assert self.kls(".".join(["blah"] * 10))(m) == m
        with pytest.raises(AttributeError):
            self.kls("foon.dar")(m)


class Test_jit_attr:
    kls = staticmethod(_internal_jit_attr)

    @property
    def jit_attr(self):
        return partial(klass.jit_attr, kls=self.kls)

    @property
    def jit_attr_named(self):
        return partial(klass.jit_attr_named, kls=self.kls)

    @property
    def jit_attr_ext_method(self):
        return partial(klass.jit_attr_ext_method, kls=self.kls)

    def mk_inst(
        self,
        attrname="_attr",
        method_lookup=False,
        use_cls_setattr=False,
        func=None,
        singleton=_uncached_singleton,
    ):
        f = func
        if not func:

            def f(self):
                self._invokes.append(self)
                return 54321

        class cls:
            def __init__(self):
                sf = partial(object.__setattr__, self)
                sf("_sets", [])
                sf("_reflects", [])
                sf("_invokes", [])

            attr = self.kls(f, attrname, singleton, use_cls_setattr)

            def __setattr__(self, attr, value):
                self._sets.append(self)
                object.__setattr__(self, attr, value)

            def reflect(self):
                self._reflects.append(self)
                return 12345

        return cls()

    def assertState(self, instance, sets=0, reflects=0, invokes=0, value=54321):
        assert instance.attr == value
        sets = [instance] * sets
        reflects = [instance] * reflects
        invokes = [instance] * invokes
        msg = (
            "checking %s: got(%r), expected(%r); state was sets=%r, "
            "reflects=%r, invokes=%r"
            % ("%s", "%s", "%s", instance._sets, instance._reflects, instance._invokes)
        )
        assert instance._sets == sets, msg % ("sets", instance._sets, sets)
        assert instance._reflects == reflects, msg % (
            "reflects",
            instance._reflects,
            reflects,
        )
        assert instance._invokes == invokes, msg % (
            "invokes",
            instance._invokes,
            invokes,
        )

    def test_implementation(self):
        obj = self.mk_inst()

        # default state is use_cls_setattr = False
        self.assertState(obj, invokes=1)
        self.assertState(obj, invokes=1)
        del obj._attr
        self.assertState(obj, invokes=2)
        self.assertState(obj, invokes=2)

        # basic caching is now verified.
        obj = self.mk_inst(use_cls_setattr=True)
        self.assertState(obj, sets=1, invokes=1)
        self.assertState(obj, sets=1, invokes=1)
        del obj._attr
        self.assertState(obj, sets=2, invokes=2)
        self.assertState(obj, sets=2, invokes=2)

    def test_jit_attr(self):
        now = time()

        class cls:
            @self.jit_attr
            def my_attr(self):
                return now

        o = cls()
        assert o.my_attr == now
        assert o._my_attr == now

        class cls:
            @self.jit_attr
            def attr2(self):
                return now

            def __setattr__(self, attr, value):
                raise AssertionError("setattr was invoked")

        o = cls()
        assert o.attr2 == now
        assert o._attr2 == now
        del o._attr2
        assert o.attr2 == now
        assert o._attr2 == now

    def test_jit_attr_named(self):
        now = time()

        # check attrname control and default object.__setattr__ avoidance
        class cls:
            @self.jit_attr_named("_blah")
            def my_attr(self):
                return now

            def __setattr__(self, attr, value):
                raise AssertionError("setattr was invoked")

        o = cls()
        assert o.my_attr == now
        assert o._blah == now

        class cls:
            @self.jit_attr_named("_blah2", use_cls_setattr=True)
            def my_attr(self):
                return now

            def __setattr__(self, attr, value):
                object.__setattr__(self, "invoked", True)
                object.__setattr__(self, attr, value)

        o = cls()
        assert not hasattr(o, "invoked")
        assert o.my_attr == now
        assert o._blah2 == now
        assert o.invoked

    def test_jit_attr_ext_method(self):
        now = time()
        now2 = now + 100

        class base:
            def f1(self):
                return now

            def f2(self):
                return now2

            def __setattr__(self, attr, value):
                if not getattr(self, "_setattr_allowed", False):
                    raise TypeError("setattr isn't allowed for %s" % attr)
                object.__setattr__(self, attr, value)

        base.attr = self.jit_attr_ext_method("f1", "_attr")
        o = base()
        assert o.attr == now
        assert o._attr == now
        assert o.attr == now

        base.attr = self.jit_attr_ext_method("f1", "_attr", use_cls_setattr=True)
        o = base()
        with pytest.raises(TypeError):
            getattr(o, "attr")
        base._setattr_allowed = True
        assert o.attr == now

        base.attr = self.jit_attr_ext_method("f2", "_attr2")
        o = base()
        assert o.attr == now2
        assert o._attr2 == now2

        # finally, check that it's doing lookups rather then storing the func.
        base.attr = self.jit_attr_ext_method("func", "_attr2")
        o = base()
        # no func...
        with pytest.raises(AttributeError):
            getattr(o, "attr")
        base.func = base.f1
        assert o.attr == now
        assert o._attr2 == now
        # check caching...
        base.func = base.f2
        assert o.attr == now
        del o._attr2
        assert o.attr == now2

    def test_check_singleton_is_compare(self):
        def throw_assert(*args, **kwds):
            raise AssertionError(
                "I shouldn't be invoked: %s, %s"
                % (
                    args,
                    kwds,
                )
            )

        class puker:
            __eq__ = throw_assert

        puker_singleton = puker()

        obj = self.mk_inst(singleton=puker_singleton)
        obj._attr = puker_singleton
        # force attr access. if it's done wrong, it'll puke.
        # pylint: disable=pointless-statement
        obj.attr

    def test_cached_property(self):
        l = []  # noqa: E741

        class foo:
            @klass.cached_property
            def blah(self, l=l, i=iter(range(5))):  # noqa: E741
                l.append(None)
                return next(i)

        f = foo()
        assert f.blah == 0
        assert len(l) == 1
        assert f.blah == 0
        assert len(l) == 1
        del f.blah
        assert f.blah == 1
        assert len(l) == 2


class Test_aliased_attr:
    func = staticmethod(klass.alias_attr)

    def test_it(self):
        class cls:
            attr = self.func("dar.blah")

        o = cls()
        with pytest.raises(AttributeError):
            getattr(o, "attr")
        o.dar = "foon"

        with pytest.raises(AttributeError):
            getattr(o, "attr")
        o.dar = o
        o.blah = "monkey"

        assert o.attr == "monkey"

        # verify it'll cross properties...
        class blah:
            target = object()

        class cls:
            @property
            def foon(self):
                return blah()

            alias = self.func("foon.target")

        o = cls()
        assert o.alias is blah.target


class Test_cached_hash:
    func = staticmethod(klass.cached_hash)

    def test_it(self):
        now = int(time())

        class cls:
            invoked = []

            @self.func
            def __hash__(self):
                self.invoked.append(self)
                return now

        o = cls()
        assert hash(o) == now
        assert o.invoked == [o]
        # ensure it cached...
        assert hash(o) == now
        assert o.invoked == [o]
        assert o._hash == now


class Test_reflective_hash:
    func = staticmethod(klass.reflective_hash)

    def test_it(self):
        class cls:
            __hash__ = self.func("_hash")

        obj = cls()
        with pytest.raises(AttributeError):
            hash(obj)
        obj._hash = 1
        assert hash(obj) == 1
        obj._hash = 123123123
        assert hash(obj) == 123123123
        # verify it's not caching in any form
        del obj._hash
        with pytest.raises(AttributeError):
            hash(obj)

        class cls2:
            __hash__ = self.func("_dar")

        obj = cls2()
        with pytest.raises(AttributeError):
            hash(obj)
        obj._dar = 4
        assert hash(obj) == 4


class TestImmutableInstance:
    def test_metaclass(self):
        with deprecated_call():
            self.common_test(lambda x: x, metaclass=klass.immutable_instance)

    def test_injection(self):
        def f(scope):
            with deprecated_call():
                klass.inject_immutable_instance(scope)

        self.common_test(f)

    def common_test(self, modify_kls, **kwargs):
        class kls(**kwargs):
            modify_kls(locals())

        o = kls()
        with pytest.raises(AttributeError):
            setattr(o, "dar", "foon")
        with pytest.raises(AttributeError):
            delattr(o, "dar")

        object.__setattr__(o, "dar", "foon")
        with pytest.raises(AttributeError):
            delattr(o, "dar")

        # ensure it only sets it if nothing is in place already.

        class kls(**kwargs):
            def __setattr__(self, attr, value):
                raise TypeError(self)

            modify_kls(locals())

        o = kls()
        with pytest.raises(TypeError):
            setattr(o, "dar", "foon")
        with pytest.raises(AttributeError):
            delattr(o, "dar")


class TestAliasMethod:
    func = staticmethod(klass.alias_method)

    def test_alias_method(self):
        class kls:
            __len__ = lambda s: 3  # noqa: E731
            lfunc = self.func("__len__")

        c = kls()
        assert c.__len__() == c.lfunc()
        c.__len__ = lambda: 4
        assert c.__len__() == c.lfunc()


class TestGenericEquality:
    def test_it(self):
        class still_abc(klass.GenericEquality):
            pass

        try:

            class foo(still_abc):
                pass

            foo()
            pytest.fail(
                "GenericEquality subclass check didn't require __attr_comparison__ to be set in the class"
            )
        except TypeError:
            pass

        class kls(klass.GenericEquality):
            __attr_comparison__ = ("x", "y")

            def __init__(self, x, y, **vals):
                self.x = x
                self.y = y
                for k, v in vals.items():
                    setattr(self, k, v)

        assert kls(1, 2) == kls(1, 2)
        assert kls(1, 2) != kls(2, 1)
        assert kls(1, 2) == kls(1, 2, z="3"), (
            "__eq__ invalidly check z, which is not in the __attr__comparison__"
        )
        # assert it's not sensitive to None
        assert kls(1, None) == kls(1, None)
        assert kls(1, 2) != kls(None, 2)

        obj1, obj2 = kls(1, 2), kls(1, 2)
        del obj1.x
        assert obj1 != obj2, "obj1.x doesn't exist, this should fail"
        del obj2.x
        assert obj1 == obj2, ".x is missing on both, they should be equal"

    def test_compare_slots(self):
        class kls1(klass.GenericEquality, compare_slots=True):
            __slots__ = ("a",)

        with pytest.raises(TypeError):

            class kls2(kls1, compare_slots=True): ...

        class kls3(kls1, compare_slots=True):
            __slots__ = ()

        assert ("a",) == kls3.__attr_comparison__

        class kls4(kls3):
            __slots__ = ("c",)

        class kls5(kls4, compare_slots=True):
            __slots__ = "b"

        assert ("b", "c", "a") == kls5.__attr_comparison__


class TestGenericRichComparison:
    def test_it(self):
        class kls(klass.GenericRichComparison):
            __attr_comparison__ = ("x", "y")

            def __init__(self, x=1, y=2):
                self.x, self.y = x, y

        obj1 = kls()
        # these use identity check shortcuts, validate how it handles
        # the same instance.
        assert obj1 == obj1
        assert obj1 <= obj1
        assert obj1 >= obj1
        assert not (obj1 < obj1)
        assert not (obj1 > obj1)
        assert not (obj1 != obj1)

        # validate the usual scenarios
        obj2 = kls()
        assert not (obj1 < obj2)
        assert obj1 <= obj2
        assert not (obj1 != obj2)
        assert obj1 >= obj2
        assert not (obj1 > obj2)

        obj1.x = 0
        assert obj1 < obj2
        assert obj1 <= obj2
        assert not (obj1 > obj2)
        assert not (obj1 >= obj2)

        del obj1.x
        assert obj1 != obj2
        assert obj1 < obj2
        assert obj1 <= obj2
        assert not (obj1 > obj2)
        assert not (obj1 >= obj2)


def test_abstractclassvar():
    class kls1(abc.ABC): ...

    assert not inspect.isabstract(kls1)  # nothing abstract in it, despite the base

    class kls2(kls1):
        blah = klass.abstractclassvar(str)

    assert inspect.isabstract(kls2)  # no abstract bits on it

    class kls3(kls2):  # validate extending to subclasses
        ...

    assert inspect.isabstract(kls3)

    class kls4(kls3):
        blah = "asdf"

    assert not inspect.isabstract(kls4)
