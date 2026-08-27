__all__ = ("Slots", "Modules")
import sys
import typing

import pytest

from snakeoil import deprecation
from snakeoil.klass import (
    abstractclassvar,
    get_slot_of,
    get_slots_of,
    get_subclasses_of,
)

from .util import NamespaceCollector


def _qualname(target: type) -> str:
    """Name a class for a subtest id.

    Subtest ids have to be a type execnet can serialize, else the report cannot
    cross the boundary to an xdist worker and the run dies with a DumpError; a
    class object is not one of them.
    """
    return f"{getattr(target, '__module__', '?')}.{target.__qualname__}"


def _is_addressable(target: type) -> bool:
    """Is this class still reachable by name from the module it claims?

    A class its module no longer exposes isn't part of the namespace under test,
    and the shape it has is not the shape that namespace presents.  The usual
    source is ``@dataclass(slots=True)``: that builds a *replacement* class, and
    the original - which has none of the slotting the replacement gained - stays
    registered in its base's ``__subclasses__`` for the life of the process.
    """
    if (module := sys.modules.get(getattr(target, "__module__", ""), None)) is None:
        return False
    obj: typing.Any = module
    for attr in target.__qualname__.split("."):
        if attr == "<locals>":
            # defined inside a function, thus not addressable at all; take it.
            return True
        if (obj := getattr(obj, attr, None)) is None:
            return False
    return obj is target


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
            if getattr(target, "__module__", None) not in modules:
                continue
            if _is_addressable(target) and not cls.ignore_class(target):
                yield target

    @classmethod
    def ignore_class(cls, target: type) -> bool:
        """Override this if you need dynamic suppression of which classes to ignore"""
        return issubclass(target, cls.ignored_subclasses)

    def test_classes_are_collected(self):
        # everything below is a loop over collect_classes(); if that comes up
        # empty they all pass while checking nothing.
        assert list(self.collect_classes()), (
            f"no classes were collected for namespaces {self.namespaces!r}"
        )

    def test_slots_mandatory(self, subtests):
        for target in self.collect_classes():
            with subtests.test(cls=_qualname(target)):
                assert get_slot_of(target).slots is not None or getattr(
                    target, self.disable_str, False
                ), f"class has no slots nor is {self.disable_str} set to True"

    def test_shadowing(self, subtests):
        for target in self.collect_classes():
            if (slots := get_slot_of(target).slots) is None:
                continue
            with subtests.test(cls=_qualname(target)):
                # get_slot_of normalizes the names, so this has to look at what
                # the class definition actually wrote to enforce the style.
                assert isinstance(target.__dict__.get("__slots__", ()), tuple), (
                    "__slots__ must be a tuple"
                )
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
