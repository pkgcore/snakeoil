__all__ = ("ParameterizeBase", "Slots", "Modules")
import abc
import functools
import inspect
import typing
from types import ModuleType

import pytest

from snakeoil.klass.util import (
    get_slot_of,
    get_slots_of,
    get_subclasses_of,
)
from snakeoil.python_namespaces import get_submodules_of

T = typing.TypeVar("T")


class _abstractvar:
    __slots__ = ()
    __isabstractmethod__ = True


def abstractvar(_: type[T]) -> T:
    """
    mechanism to use with ClassVars to force abc.ABC to block creation if the subclass hasn't set it.

    The mechanism currently is janky; you must pass in the type definition since it's the
    only way to attach this information to the returned object, lieing to the type system
    that the value is type compatible while carrying the marker abc.ABC needs.
    """
    return typing.cast(T, _abstractvar())


class ParameterizeBase(typing.Generic[T], abc.ABC):
    namespaces: typing.ClassVar[tuple[str]] = abstractvar(tuple[str])
    namespace_ignores: tuple[str, ...] = ()
    strict: tuple[str] | bool = False
    tests_to_parameterize: typing.ClassVar[tuple[str, ...]] = abstractvar(tuple[str])

    @classmethod
    @abc.abstractmethod
    def make_id(cls, /, param: T) -> str: ...

    @classmethod
    @abc.abstractmethod
    def collect_parameters(cls, modules: set[ModuleType]) -> typing.Iterable[T]: ...

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()

        if inspect.isabstract(cls):
            return

        # Inject the parameterization
        targets = list(
            sorted(cls.collect_parameters(set(cls.collect_modules())), key=cls.make_id)
        )

        for test in cls.tests_to_parameterize:
            original = getattr(cls, test)

            @pytest.mark.parametrize(
                "param",
                targets,
                ids=cls.make_id,
            )
            @functools.wraps(original)
            def do_it(self, param: T, original=original):
                return original(self, param)

            if not cls.is_strict_test(test):
                do_it = pytest.mark.xfail(strict=False)(do_it)
            setattr(cls, test, do_it)

        super().__init_subclass__()

    @classmethod
    def is_strict_test(cls, test_name: str) -> bool:
        if isinstance(cls.strict, bool):
            return cls.strict
        return test_name in cls.strict

    @classmethod
    def collect_modules(cls) -> typing.Iterable[ModuleType]:
        for namespace in cls.namespaces:
            yield from get_submodules_of(
                __import__(namespace), dont_import=cls.namespace_ignores
            )


class Slots(ParameterizeBase[type]):
    disable_str: typing.Final = "__slotting_intentionally_disabled__"
    ignored_subclasses: tuple[type, ...] = (Exception,)

    tests_to_parameterize = (
        "test_shadowing",
        "test_slots_mandatory",
    )

    @classmethod
    def make_id(cls, param: type) -> str:
        return f"{param.__module__}.{param.__qualname__}"

    @classmethod
    def collect_parameters(cls, modules) -> typing.Iterable[type]:
        modules = set(x.__name__ for x in modules)
        for target in get_subclasses_of(object):
            if not cls.ignore_module(target, modules) and not cls.ignore_class(target):
                yield target

    @classmethod
    def ignore_module(cls, target: type, collected_modules: typing.Container[str]):
        """Override if you need custom logic for the module filter of classes"""
        return target.__module__ not in collected_modules

    @classmethod
    def ignore_class(cls, target: type) -> bool:
        """Override this if you need dynamic suppression of which classes to ignore"""
        return issubclass(target, cls.ignored_subclasses)

    def test_slots_mandatory(self, param: type):
        assert get_slot_of(param).slots is not None or getattr(
            param, self.disable_str, False
        ), f"class has no slots nor is {self.disable_str} set to True"

    def test_shadowing(self, param: type):
        if (slots := get_slot_of(param).slots) is None:
            return
        assert isinstance(slots, tuple), "__slots__ must be a tuple"
        slots = set(slots)
        for slotting in get_slots_of(param):
            if slotting.cls is param:
                continue
            if slotting.slots is not None:
                assert set() == slots.intersection(slotting.slots), (
                    f"has slots that shadow {param}"
                )


class Modules(ParameterizeBase[ModuleType]):
    tests_to_parameterize = (
        "test_has__all__",
        "test_valid__all__",
    )
    strict = ("test_valid__all__",)

    @classmethod
    def make_id(cls, /, param: ModuleType) -> str:
        return param.__name__

    @classmethod
    def collect_parameters(cls, modules) -> typing.Iterable[ModuleType]:
        return modules

    def test_has__all__(self, param: ModuleType):
        assert hasattr(param, "__all__"), "__all__ is missing but should exist"

    def test_valid__all__(self, param: ModuleType):
        if attrs := getattr(param, "__all__", ()):
            missing = {attr for attr in attrs if not hasattr(param, attr)}
            assert not missing, (
                f"__all__ refers to exports that don't exist: {missing!r}"
            )
