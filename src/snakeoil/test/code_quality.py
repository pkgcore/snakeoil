__all__ = ("NamespaceCollector", "Slots", "Modules")
import inspect
import typing
from types import ModuleType

import pytest

from snakeoil import deprecation
from snakeoil.klass import (
    abstractclassvar,
    get_slot_of,
    get_slots_of,
    get_subclasses_of,
)
from snakeoil.python_namespaces import get_submodules_of
from snakeoil.test import AbstractTest

T = typing.TypeVar("T")


class NamespaceCollector(AbstractTest):
    namespaces: tuple[str] = abstractclassvar(tuple[str])
    namespace_ignores: tuple[str, ...] = ()

    strict_configurable_tests: typing.ClassVar[tuple[str, ...]] = ()
    strict: typing.ClassVar[typing.Literal[True] | tuple[str, ...]] = ()

    def __init_subclass__(cls, **kwargs) -> None:
        if not inspect.isabstract(cls):
            targets = cls.strict_configurable_tests
            strict = targets if cls.strict is True else cls.strict
            for test_name in cls.strict_configurable_tests:
                if test_name not in strict:
                    setattr(cls, test_name, pytest.mark.xfail(getattr(cls, test_name)))

        return super().__init_subclass__(**kwargs)

    @classmethod
    def collect_modules(cls) -> typing.Iterable[ModuleType]:
        for namespace in cls.namespaces:
            yield from get_submodules_of(
                namespace,
                dont_import=cls.namespace_ignores,
                include_root=True,
            )


class Slots(NamespaceCollector, still_abstract=True):
    disable_str: typing.Final = "__slotting_intentionally_disabled__"
    ignored_subclasses: tuple[type, ...] = (
        Exception,
        typing.Protocol,  # pyright: ignore[reportAssignmentType]
    )

    strict_configurable_tests = (
        "test_shadowing",
        "test_slots_mandatory",
    )

    @classmethod
    def collect_classes(cls) -> typing.Iterable[type]:
        modules = set(x.__name__ for x in cls.collect_modules())
        for target in get_subclasses_of(object):
            if cls.__module__ in modules and not cls.ignore_class(target):
                yield target

    @classmethod
    def ignore_class(cls, target: type) -> bool:
        """Override this if you need dynamic suppression of which classes to ignore"""
        return issubclass(target, cls.ignored_subclasses)

    def test_slots_mandatory(self, subtests):
        for target in self.collect_classes():
            with subtests.test(cls=target):
                assert get_slot_of(target).slots is not None or getattr(
                    target, self.disable_str, False
                ), f"class has no slots nor is {self.disable_str} set to True"

    def test_shadowing(self, subtests):
        for target in self.collect_classes():
            if (slots := get_slot_of(target).slots) is None:
                return
            with subtests.test(cls=target):
                assert isinstance(slots, tuple), "__slots__ must be a tuple"
                slots = set(slots)
                for slotting in get_slots_of(target):
                    if slotting.cls is target:
                        continue
                    if slotting.slots is not None:
                        assert set() == slots.intersection(slotting.slots), (
                            f"has slots that shadow {target}"
                        )


class Modules(NamespaceCollector, still_abstract=True):
    strict_configurable_tests = (
        "test_has__all__",
        "test_valid__all__",
    )
    strict = ("test_valid__all__",)

    def test_has__all__(self, subtests):
        for module in self.collect_modules():
            with subtests.test(module=module.__name__):
                assert hasattr(module, "__all__"), "__all__ is missing but should exist"

    def test_valid__all__(self, subtests):
        with deprecation.suppress_deprecations():
            for module in self.collect_modules():
                with subtests.test(module=module.__name__):
                    if attrs := getattr(module, "__all__", ()):
                        missing = {attr for attr in attrs if not hasattr(module, attr)}
                        assert not missing, (
                            f"__all__ refers to exports that don't exist: {missing!r}"
                        )


class ExpiredDeprecations(NamespaceCollector, still_abstract=True):
    strict_configurable_tests = ("test_has_expired_deprecations",)
    strict = ("test_has_expired_deprecations",)

    registry: deprecation.Registry = abstractclassvar(deprecation.Registry)

    def test_has_expired_deprecations(self, subtests):
        # force full namespace load to ensure all deprecations get registry.
        with deprecation.suppress_deprecations():
            for _ in self.collect_modules():
                pass
            for deprecated in self.registry.expired_deprecations():
                with subtests.test(deprecated=str(deprecated)):
                    pytest.fail(f"deprecation has expired: {deprecated}")
