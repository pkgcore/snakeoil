import abc
import functools
import types
import typing

import pytest

from snakeoil.klass.util import (
    get_slot_of,
    get_slots_of,
    get_subclasses_of,
)
from snakeoil.python_namespaces import get_submodules_of

T = typing.TypeVar("T")


class ParameterizeTest(abc.ABC, typing.Generic[T]):
    namespaces: typing.List[str] | tuple[str]
    namespace_ignores: typing.List[str] | tuple[str, ...] = ()
    strict: typing.Container[str] | bool = False
    tests_to_parameterize: typing.ClassVar[tuple[str, ...]]

    # ABC doesn't apply to actual attributes, thus this.
    is_abstract_still: typing.ClassVar[bool] = False

    @classmethod
    @abc.abstractmethod
    def make_id(cls, /, param: T) -> str: ...

    @classmethod
    @abc.abstractmethod
    def collect_parameters(
        cls, modules: set[types.ModuleType]
    ) -> typing.Iterable[T]: ...

    def __init_subclass__(cls) -> None:
        if cls.is_abstract_still:
            del cls.is_abstract_still
            return

        if not hasattr(cls, "namespaces"):
            raise TypeError("namespaces wasn't defined on the class")
        if not hasattr(cls, "tests_to_parameterize"):
            raise TypeError("tests_to_parameterize wasn't set")

        # Inject the parameterization
        strict = (
            cls.strict
            if not isinstance(cls.strict, bool)
            else (cls.tests_to_parameterize if cls.strict else [])
        )

        targets = list(
            sorted(cls.collect_parameters(set(cls.collect_modules())), key=cls.make_id)
        )

        for test in cls.tests_to_parameterize:
            original = getattr(cls, test)

            @pytest.mark.parametrize(
                "cls",
                targets,
                ids=cls.make_id,
            )
            @functools.wraps(original)
            def do_it(self, cls: type, original=original):
                return original(self, cls)

            if test not in strict:
                do_it = pytest.mark.xfail(strict=False)(do_it)
            setattr(cls, test, do_it)

        super().__init_subclass__()

    @classmethod
    def collect_modules(cls) -> typing.Iterable[types.ModuleType]:
        for namespace in cls.namespaces:
            yield from get_submodules_of(
                __import__(namespace), dont_import=cls.namespace_ignores
            )


class Slots(ParameterizeTest[type]):
    disable_str: typing.Final = "__slotting_intentionally_disabled__"
    ignored_subclasses: tuple[type, ...] = (Exception,)

    is_abstract_still = True

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

    def test_slots_mandatory(self, cls: type):
        assert get_slot_of(cls).slots is not None or getattr(
            cls, self.disable_str, False
        ), f"class has no slots nor is {self.disable_str} set to True"

    def test_shadowing(self, cls: type):
        if (slots := get_slot_of(cls).slots) is None:
            return
        assert isinstance(slots, tuple), "__slots__ must be a tuple"
        slots = set(slots)
        for slotting in get_slots_of(cls):
            if slotting.cls is cls:
                continue
            if slotting.slots is not None:
                assert set() == slots.intersection(slotting.slots), (
                    f"has slots that shadow {cls}"
                )
