import abc
import gc
from inspect import isabstract

import pytest

from snakeoil import klass
from snakeoil.containers import Unchangable
from snakeoil.klass import memoize


class TestWeakInstMeta:
    def test_reuse_logic(self):
        class cached(memoize.WeaklyCached): ...

        class disabled(memoize.WeaklyCached, caching=False): ...

        o = cached()
        assert o is cached()
        assert o is not cached(disable_inst_caching=True), (
            "disable_inst_caching=True must suppress reuse, and this didn't"
        )
        assert o is cached(disable_inst_caching=False)

        address = id(o)
        del o
        gc.collect()
        assert address is not id(cached()), (
            "the previous memory address of the cached instance is the same as the new instance, despite deleting it and forcing GC collect.  This shouldn't exist per python GC rules."
        )

        o = disabled()
        assert o is not disabled(), (
            "disabled class has instance caching off, yet it returned the previous instance having the same args/kwargs.  Disable mechanism didn't work"
        )
        assert o is not disabled(disable_inst_caching=True)

    def test_class_definitions(self, recwarn):
        assert not memoize.WeaklyCached.__tolerate_uncachable_args__, (
            "the default of not tolerating uncachable args and kwargs isn't disabled"
        )
        assert memoize.WeaklyCached.__child_instance_caching_default__, (
            "the default of all children classes having instance caching isn't enabled"
        )

        class base(memoize.WeaklyCached):
            __slots__ = ()  # no weakref- we're verifying it exists

        # the `x.slots is not None` filter is just to shut up ruff- slots are guaranteed for this class.
        assert any(
            "__weakref__" in x.slots
            for x in klass.get_slots_of(base)
            if x.slots is not None
        )
        assert not base.__tolerate_uncachable_args__, (
            "default of erroring for any uncachable init args wasn't set"
        )
        assert base.__child_instance_caching_default__, (
            "default of instance caching being enabled wasn't set"
        )

        assert base.__instance_cache__ is not None

        class foo2(base, caching=False):
            __slots__ = ()

        assert foo2.__instance_cache__ is None
        assert foo2.__tolerate_uncachable_args__ == base.__tolerate_uncachable_args__, (
            "the child disabled caching, but the parents directive of 'prohibit uncachable args' was not preserved."
        )
        assert not foo2.__child_instance_caching_default__, (
            "instance caching was disabled but the default for children wasn't set to disabled"
        )
        o = foo2()
        assert o is not foo2()

        class foo3(foo2, caching=True):
            __slots__ = ()

        assert foo3.__instance_cache__ is not None, (
            "explicit caching=True class argument didn't result in an instance cache"
        )
        assert not foo3.__tolerate_uncachable_args__, (
            "unchachable warning was not reset back to enforced when instance caching was turned back on for a child class"
        )
        assert foo3.__child_instance_caching_default__, (
            "re-enabling of caching did not re-enable caching for the child"
        )

        assert 1 == len(
            list(
                1
                for x in klass.get_slots_of(foo3)
                if "__weakref__" in x.slots  # type: ignore
            )
        ), "The base classes's __weakref__ slot is missing, and must be added"  # type: ignore

        class abc1(base, memoize.WeaklyCachedABC):
            @abc.abstractmethod
            def undefined(self): ...

        assert isabstract(abc1)
        assert abc1.__child_instance_caching_default__, (
            "abc overeode the parents default of enabling instance caching"
        )
        assert not abc1.__tolerate_uncachable_args__, (
            "abc overrode the parents default of not tolerating uncachable args"
        )
        assert abc1.__instance_cache__ is None, (
            "abstract classes can't be instantiated, however an instance cache was created"
        )

        class abc2(abc1, caching=False, tolerate_uncachable_args=True): ...

        assert not abc2.__child_instance_caching_default__, (
            "ABC class changing of child class caching default wasn't honored"
        )
        assert abc2.__tolerate_uncachable_args__, (
            "ABC class changing of child class toleration of uncachable args wasn't honored"
        )

        class NotABC(abc1):
            def undefined(self): ...

        assert not isabstract(NotABC)
        assert (
            NotABC.__child_instance_caching_default__
            == abc1.__child_instance_caching_default__
        )
        assert NotABC.__tolerate_uncachable_args__ == abc1.__tolerate_uncachable_args__
        assert NotABC.__instance_cache__ is not None

    def test_instance_uncachable_logic(self, recwarn):
        class strict(memoize.WeaklyCached):
            def __init__(self, *args, **kwargs): ...

        # ensure explosion if not tolerated
        with pytest.raises(TypeError):
            strict([1])  # pyright: ignore[reportArgumentType]

        assert 0 == len(recwarn)

        # tolerate but warn
        class tolerate(strict, tolerate_uncachable_args=True): ...

        assert tolerate.__tolerate_uncachable_args__

        tolerate([1])  # pyright: ignore[reportArgumentType]
        assert 1 == len(recwarn)

        tolerate(blah=[1])  # pyright: ignore[reportArgumentType]
        assert 2 == len(recwarn)

        tolerate(1, [2], blah=[1])  # pyright: ignore[reportArgumentType]
        assert 3 == len(recwarn)

        # assert quality of life- the exception stating *which* argument.
        msg = str(recwarn[2])
        assert "blah=" in msg
        assert "argument 1 value=" in msg
