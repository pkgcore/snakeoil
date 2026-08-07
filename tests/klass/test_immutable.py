import contextvars
import copy
import pickle
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


class _slotted(immutable.Simple):
    __slots__ = ("__weakref__", "x", "y")

    def __init__(self, x, y=None):
        self.x = x
        if y is not None:
            self.y = y


class _strict_slotted(immutable.Strict):
    __slots__ = ("x",)

    def __init__(self, x):
        object.__setattr__(self, "x", x)


class _mangled(immutable.Simple):
    __slots__ = ("__priv",)

    def __init__(self, value):
        self.__priv = value

    @property
    def priv(self):
        return self.__priv


class _dicted(immutable.Simple):
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            object.__setattr__(self, k, v)


class _mixed(_dicted):
    __slots__ = ("x",)

    def __init__(self, x, **kwargs):
        super().__init__(**kwargs)
        self.x = x


class TestMarshalling(metaclass=inject_context_protection):
    """Instances must survive pickle/copy despite the mutation protections"""

    def roundtrips(self, obj):
        yield copy.copy(obj)
        yield copy.deepcopy(obj)
        for protocol in (2, pickle.HIGHEST_PROTOCOL):
            yield pickle.loads(pickle.dumps(obj, protocol))

    def test_slotted(self):
        for obj in self.roundtrips(_slotted(1, 2)):
            assert (obj.x, obj.y) == (1, 2)

    def test_strict(self):
        for obj in self.roundtrips(_strict_slotted(1)):
            assert obj.x == 1

    def test_unset_slot_stays_unset(self):
        for obj in self.roundtrips(_slotted(1)):
            assert obj.x == 1
            assert not hasattr(obj, "y")

    def test_weakref_is_not_state(self):
        _, slots = _slotted(1, 2).__getstate__()  # pyright: ignore[reportGeneralTypeIssues]
        assert "__weakref__" not in slots

    def test_mangled_slot(self):
        for obj in self.roundtrips(_mangled("dar")):
            assert obj.priv == "dar"

    def test_dicted(self):
        for obj in self.roundtrips(_dicted(a=1, b=2)):
            assert obj.a == 1 and obj.b == 2

    def test_dict_and_slots(self):
        for obj in self.roundtrips(_mixed(1, a=2)):
            assert (obj.x, obj.a) == (1, 2)

    def test_flat_slot_mapping(self):
        """state written by the deprecated klass.SlotsPicklingMixin is a flat mapping"""
        obj = _slotted.__new__(_slotted)
        obj.__setstate__({"x": 1, "y": 2})
        assert (obj.x, obj.y) == (1, 2)

    def test_foreign_state_is_rejected(self):
        """a custom __getstate__ two tuple must not be mistaken for (__dict__, slots)"""
        obj = _slotted.__new__(_slotted)
        with pytest.raises(TypeError):
            obj.__setstate__((1, "not-a-slot-mapping"))

    def test_setstate_is_not_autowrapped(self):
        for kls in (_slotted, _strict_slotted):
            assert kls.__setstate__.__disable_mutation_autowrapping__  # pyright: ignore[reportFunctionMemberAccess]

    def test_setstate_only_injected_where_needed(self):
        """a __setstate__ costs a python frame per instance; only slotting needs it"""
        assert getattr(_dicted, "__setstate__", None) is None
        assert _mixed.__setstate__ is not None

        class custom(_slotted):
            __slots__ = ()

            def __setstate__(self, state):
                raise AssertionError(state)

        assert custom.__setstate__ is not _slotted.__setstate__
