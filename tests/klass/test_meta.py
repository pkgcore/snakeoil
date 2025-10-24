import contextvars
from functools import partial, wraps

import pytest

from snakeoil.klass import combine_classes, meta


def inject_context_protection(name: str, bases: tuple[type, ...], scope) -> type:
    """
    Metaclass to force all test methods to be burried in a context.run

    Pushing a context onto the stack is only possible in wrapping a callable,
    thus fixtures can't be used for this.
    """

    def closure(functor):
        @wraps(functor)
        def f(self, *args, **kwargs):
            return push_context(functor)(self, *args, **kwargs)

        return f

    for k, v in scope.items():
        if k.startswith("test_"):
            scope[k] = closure(v)
    return type(name, bases, scope)


def push_context(functor):
    """Used as both decorator and invokable, this pushes a context on the stack"""
    return partial(contextvars.Context().run, functor)


class TestInjectContextProtection(metaclass=inject_context_protection):
    """Verify that the protective measures used for these tests actually work"""

    context_protection_test_var = contextvars.ContextVar("metaclass-validation")

    def test_inject_context_protection_step1(self):
        singleton = object()
        assert singleton == self.context_protection_test_var.get(singleton)
        self.context_protection_test_var.set(1)

    def test_inject_context_protection_step2(self):
        singleton = object()
        assert singleton == self.context_protection_test_var.get(singleton)
        self.context_protection_test_var.set(2)


class TestSimpleImmutable(metaclass=inject_context_protection):
    class _immutable_test_kls(metaclass=meta.Immutable):
        def __init__(self, recurse=False):
            self.dar = 1
            if recurse:
                o = self.__class__(False)
                # assert the child is immutable now.
                pytest.raises(AttributeError, setattr, o, "dar", 4)
                self.dar = 3

        @meta.Immutable.allow_mutation
        def set_dar(self, value: int) -> None:
            self.dar = value

    def test_injection(self):
        def init(self):
            self.x = 1

        def setstate(self, data):
            self.x = data

        class foo(metaclass=meta.Immutable):
            __init__ = init

        assert foo.__init__ is not init

        class foo2(foo):
            __setstate__ = setstate

        assert foo.__init__ is foo2.__init__
        assert foo2.__setstate__ is not setstate

        # ensure that we're not daftly injecting extra instances of the default class logic.
        # this is required to ensure we're not overriding things further down mro.
        assert len([x for x in foo.mro() if x == meta.Immutable.Mixin]) == 1
        assert len([x for x in foo2.mro() if x == meta.Immutable.Mixin]) == 1

    def test_mutation_init(self):
        o = self._immutable_test_kls()
        assert o.dar == 1
        pytest.raises(AttributeError, lambda: setattr(o, "x", 1))

    def test_mutation_recursion(self):
        """validate the internal bookkeeping in the face of recursion

        Specifically, if during an immutable instance's __init__ it generates another immutable instance,
        the child must work, as must the parent be able to mutate after exiting that child init.
        """
        assert self._immutable_test_kls(recurse=True).dar == 3, (
            "assert recursion support for immutable instances creating immutable instances w/in mutation blocks"
        )

    def test_mutation_utilities(self):
        o = self._immutable_test_kls()
        assert o.dar == 1
        o.set_dar(5)
        assert o.dar == 5
        with o.__allow_mutation_block__():
            o.dar = 6
        assert o.dar == 6

    def test_mutation_contextvars_assumptions(self):
        """validate the underlying codes assumptions about how contextvars works

        Whilst this is anal, if this fails, either the python implementation differs from cpython,
        or cpython changed.  Fix this first before trying to fix any other tests.
        """
        var = contextvars.ContextVar("test", default=1)

        @push_context
        def basic():
            assert 1 == var.get()
            var.set(2)

        basic()
        assert 1 == var.get()

        @push_context
        def generator(val=2):
            assert 1 == var.get()
            var.set(2)
            yield
            assert val == var.get()

        # verify that generators on their own don't switch context.
        for _ in generator():  # type: ignore[reportCallIssue]
            assert 2 == var.get(), (
                "generator context wasn't shared.  Was PEP568 implemented?"
            )
        del var


def test_combine_metaclasses():
    class kls1(type):
        pass

    class kls2(type):
        pass

    class kls3(type):
        pass

    # assert it requires at least one arg
    pytest.raises(TypeError, combine_classes)

    assert combine_classes(kls1) is kls1, "unneeded derivative metaclass was created"

    # assert that it refuses duplicats
    pytest.raises(TypeError, combine_classes, kls1, kls1)

    # there is caching, thus also do identity check whilst checking the MRO chain
    kls = combine_classes(kls1, kls2, kls3)
    assert kls is combine_classes(kls1, kls2, kls3), (
        "combine_metaclass uses lru_cache to avoid generating duplicate classes, however this didn't cache"
    )

    combined = combine_classes(kls1, kls2)
    assert [combined, kls1, kls2, type, object] == list(combined.__mro__)
