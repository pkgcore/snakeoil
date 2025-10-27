import contextvars
from functools import partial, wraps

import pytest

from snakeoil.klass import immutable


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
    class _immutable_test_kls(immutable.Simple):
        def __init__(self, recurse=False):
            self.dar = 1
            if recurse:
                o = self.__class__(False)
                # assert the child is immutable now.
                pytest.raises(AttributeError, setattr, o, "dar", 4)
                self.dar = 3

        @immutable.Simple.__allow_mutation_wrapper__
        def set_dar(self, value: int) -> None:
            self.dar = value

    def test_injection(self):
        def init(self):
            self.x = 1

        def setstate(self, data):
            self.x = data

        class foo(immutable.Simple):
            __init__ = init

        assert foo.__init__.__disable_mutation_autowrapping__  # pyright: ignore[reportFunctionMemberAccess]
        assert foo.__init__ is not init

        class foo2(foo):
            __setstate__ = setstate

        assert foo.__init__ is foo2.__init__
        assert foo2.__setstate__ is not setstate

        def self_mutation_managing_init(self):
            pass

        self_mutation_managing_init.__disable_mutation_autowrapping__ = True  # pyright: ignore[reportFunctionMemberAccess]

        class foo3(foo2):
            __init__ = self_mutation_managing_init

        assert foo3.__init__ is self_mutation_managing_init, (
            "__init__ was marked to not be wrapped, but got wrapped anyways"
        )

    def test_disallowed_mutation(self):
        class kls(immutable.Simple):
            pass

        obj = kls()
        pytest.raises(AttributeError, setattr, obj, "x", 1)
        pytest.raises(AttributeError, delattr, obj, "y")

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
        with o.__allow_mutation__():
            o.dar = 6
        assert o.dar == 6

    def test_mutation_contextvars_assumptions(self):
        """validate the underlying codes assumptions about how contextvars works

        Whilst this is anal, if this fails, either the python implementation differs from cpython,
        or cpython changed.  Fix this first before trying to fix any other tests.
        """
        var = contextvars.ContextVar("test", default=1)

        @push_context
        def basic(var=var):
            assert 1 == var.get()
            var.set(2)

        basic()
        assert 1 == var.get()

        @push_context
        def generator(val=2, var=var):
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


class TestStrict:
    def _common(self, slotted=False):
        class kls(immutable.Strict):
            if slotted:
                __slots__ = ("x",)

            def m(self):
                self.x = 1

        obj = kls()
        pytest.raises(AttributeError, setattr, obj, "x", 2)
        pytest.raises(AttributeError, delattr, obj, "x")
        if slotted:
            pytest.raises(AttributeError, setattr, obj, "y", 2)
            pytest.raises(AttributeError, delattr, obj, "y")

        kls.__init__ = kls.m
        pytest.raises(AttributeError, kls)

    def test_basics(self):
        self._common()
        self._common(slotted=True)
