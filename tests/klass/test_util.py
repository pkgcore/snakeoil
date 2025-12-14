import abc
import gc
import operator
import weakref
from typing import Any

import pytest

from snakeoil.klass.util import (
    ClassSlotting,
    combine_metaclasses,
    get_attrs_of,
    get_instances_of,
    get_slots_of,
    get_subclasses_of,
    is_metaclass,
)


class Test_get_attrs_of:
    def test_reason_for_existing(self):
        # This exists to detect when python fixes the vars() issue, rendering get_attrs_of redundant.
        class foon:
            __slots__ = ("x", "y")

        inst = foon()
        inst.x, inst.y = 1, 2
        with pytest.raises(TypeError):
            vars(inst)

        class with_dict(foon): ...

        inst = with_dict()
        inst.x, inst.y = (1, 2)
        assert [] == list(vars(inst))
        # Push something into the __dict__
        inst.z = 3  # pyright: ignore[reportAttributeAccessIssue]
        assert ["z"] == list(vars(inst))

    def test_it(self):
        def _assert_no_duplicates(obj, **kwds):
            seen = set()
            for k, v in get_attrs_of(obj, **kwds):
                assert k not in seen, "duplicate attributes must not be returned"
                yield k, v
                seen.add(k)

        def assert_attrs(o, result, **kwds):
            assert result == dict(_assert_no_duplicates(o, **kwds))

        def mk_obj(parent=object, slots=None, create=False) -> Any:
            class kls(parent):
                if slots is not None:
                    locals()["__slots__"] = (
                        (slots,) if isinstance(slots, str) else tuple(slots)
                    )

            if not create:
                return kls
            obj = kls()
            assert_attrs(obj, {})
            return obj

        # make a pure chained slotted class
        obj = mk_obj(mk_obj(slots="x"), "y", create=True)
        obj.x = 1
        assert_attrs(obj, {"x": 1})
        obj.y = 2
        assert_attrs(obj, {"x": 1, "y": 2})
        # verify the reverse direction out of paranoia.
        del obj.x
        assert_attrs(obj, {"y": 2})

        # verify it handles shadowed slots
        obj = mk_obj(mk_obj(slots="x"), slots="x", create=True)  # x is shadowed
        obj.x = 1
        assert_attrs(obj, {"x": 1})

        # ...verify it handles layered __slots__ that normal visibility of the underlying
        # slot, even if it's still a usable attribute
        obj = mk_obj(mk_obj(slots="x"), slots=(), create=True)

        # the fun one.  Mixed slotting.
        obj = mk_obj(mk_obj(), slots="x", create=True)
        obj.x = 1
        assert "x" not in obj.__dict__, (
            "a slotted variable was tucked into __dict__; this is not how python is understood to work for this code.  While real code can do this- it's dumb but possible- this test doesn't do that, thus something is off."
        )
        assert_attrs(obj, {"x": 1})
        obj.y = 2
        assert_attrs(obj, {"x": 1, "y": 2})

        # check weakref and suppression
        obj = mk_obj(create=True)
        ref = weakref.ref(obj)
        assert_attrs(obj, {})

        assert_attrs(obj, {"__weakref__": ref}, weakref=True)
        obj.blah = 1
        assert_attrs(obj, {}, suppressions=["blah"])


def test_slots_of():
    # the bulk of this logic is already flxed by get_attrs_of.  Just assert the api.
    class kls1:
        __slots__ = ("x",)

    class kls2(kls1):
        pass

    class kls3(kls2):
        __slots__ = ()

    class kls4(kls3):
        __slots__ = ("y",)

    assert [
        ClassSlotting(kls4, ("y",)),
        ClassSlotting(kls3, ()),
        ClassSlotting(kls2, None),
        ClassSlotting(kls1, ("x",)),
        ClassSlotting(object, ()),
    ] == list(get_slots_of(kls4))


def test_combine_metaclasses():
    class kls1(type):
        pass

    class kls2(type):
        pass

    class kls3(type):
        pass

    # assert it requires at least one arg
    pytest.raises(TypeError, combine_metaclasses)

    assert combine_metaclasses(kls1) is kls1, (
        "unneeded derivative metaclass was created"
    )

    # assert that it refuses duplicats
    pytest.raises(TypeError, combine_metaclasses, kls1, kls1)

    # there is caching, thus also do identity check whilst checking the MRO chain
    kls = combine_metaclasses(kls1, kls2, kls3)
    assert kls is combine_metaclasses(kls1, kls2, kls3), (
        "combine_metaclass uses lru_cache to avoid generating duplicate classes, however this didn't cache"
    )

    combined = combine_metaclasses(kls1, kls2)
    assert [combined, kls1, kls2, type, object] == list(combined.__mro__)


def test_is_metaclass():
    assert not is_metaclass(object)
    assert is_metaclass(type)

    class foon(type): ...

    assert is_metaclass(foon)


def test_get_subclasses_of():
    attr = operator.attrgetter("__name__")

    def assert_it(cls, expected, msg=None, **kwargs):
        expected = list(sorted(expected, key=attr))
        got = list(sorted(get_subclasses_of(cls, **kwargs), key=attr))
        if msg:
            assert expected == got, msg
        else:
            assert expected == got

    class layer1: ...

    class layer2(layer1): ...

    class layer3(layer2): ...

    assert_it(layer3, [])
    assert_it(layer2, [layer3])
    assert_it(layer1, [layer2, layer3])
    assert_it(layer1, [layer2, layer3], ABC=False)
    assert_it(layer1, [], ABC=True)
    assert_it(layer1, [layer3], only_leaf_nodes=True)

    class ABClayer4(abc.ABC, layer3):
        @abc.abstractmethod
        def f(self): ...

    class layer5(ABClayer4):
        def f(self):
            pass

    assert_it(layer2, [layer3, layer5], ABC=False)
    assert_it(layer2, [ABClayer4], ABC=True)
    assert_it(layer2, [], ABC=True, only_leaf_nodes=True)
    assert_it(layer2, [layer5], ABC=False, only_leaf_nodes=True)

    class ABClayer6(layer5):
        @abc.abstractmethod
        def f2(self): ...

    assert_it(layer3, [ABClayer6], ABC=True, only_leaf_nodes=True)

    # stupid diamond inheritance
    class base: ...

    class left(base): ...

    class right(base): ...

    class combined(left, right): ...

    assert_it(base, [left, right, combined])


class Test_get_instances_of:
    def test_normal(self):
        class foon: ...

        assert [] == get_instances_of(foon)
        o = foon()
        assert [o] == get_instances_of(foon)

        o2 = foon()
        assert set([o, o2]) == set(get_instances_of(foon))

    def test_verify_sees_through_thunks(self):
        """
        Parts of snakeoil infrastructure provide thunking proxies that lie *very* well.

        Specifically, if you ask them what their class is, they'll tell you they're the thing
        that they'll eventually reify.  The testing infrastructure for demandload is reliant
        on being able to see through this, thus this test asserts that get_instances_of can
        see through that.
        """

        class foo: ...

        class liar:
            def __init__(self, real):
                object.__setattr__(self, "_real", real)

            def __getattribute__(self, attr):
                return object.__getattribute__(self, "_real").__class__

            def __eq__(self, other):
                return object.__getattribute__(self, "_real") == other

        real = foo()
        # validate our setup.  Note the level of hiding it does.
        # Demandload infrastructure actually emulates the full protocol of the target's
        # cpython guts, so that hides *far* more thoroughly.  Only object.__getattribute__
        # can see through that, and python doesn't use that; certain cpython parts use an
        # equivalent, but if you can lie to isinstance... etc.
        assert foo is liar(real).__class__
        assert isinstance(liar(real), foo)
        assert real == liar(real)

        # can't lie about that one however since it's a pointer check
        assert id(real) != id(liar)
        assert real is not liar

        assert [real] == get_instances_of(foo)
        liar_obj = liar(real)
        collected = get_instances_of(liar)
        assert 1 == len(collected)
        assert liar_obj is collected[0]
