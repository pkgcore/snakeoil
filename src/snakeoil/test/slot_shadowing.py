import abc
import inspect
import typing
import warnings

import pytest

from snakeoil._internals import deprecated
from snakeoil.test.mixins import PythonNamespaceWalker


class TargetedNamespaceWalker(PythonNamespaceWalker):
    target_namespace = None

    def load_namespaces(self, namespace=None):
        if namespace is None:
            namespace = self.target_namespace
        for _mod in self.walk_namespace(namespace):
            pass


class _classWalker(abc.ABC):
    cls_blacklist = frozenset()
    collected_issues: list[str]

    @pytest.fixture(scope="function")
    @staticmethod
    def issue_collector(request):
        request.cls.collected_issues = []
        yield request.cls.collected_issues
        collected = request.cls.collected_issues
        if not collected:
            return
        collected_issues = sorted(collected)
        if getattr(request.cls, "strict"):
            s = "\n".join(collected_issues)
            pytest.fail(f"multiple failures detected:\n{s}")
        for issue in collected_issues:
            warnings.warn(issue)

    def is_blacklisted(self, cls):
        return cls.__name__ in self.cls_blacklist

    def test_object_derivatives(self, *args, issue_collector, **kwds):
        # first load all namespaces...
        self.load_namespaces()

        # next walk all derivatives of object
        for cls in self.walk_derivatives(object, *args, **kwds):
            if not self._should_ignore(cls):
                self.run_check(cls)

    def iter_builtin_targets(self):
        for attr in dir(__builtins__):
            obj = getattr(__builtins__, attr)
            if not inspect.isclass(obj):
                continue
            yield obj

    def test_builtin_derivatives(self, *args, issue_collector, **kwds):
        self.load_namespaces()
        for obj in self.iter_builtin_targets():
            for cls in self.walk_derivatives(obj, *args, **kwds):
                if not self._should_ignore(cls):
                    self.run_check(cls)

    @abc.abstractmethod
    def walk_derivatives(self, cls: typing.Type) -> typing.Iterable[typing.Type]: ...

    @abc.abstractmethod
    def run_check(self, cls: type) -> None: ...

    def report_issue(self, message):
        self.collected_issues.append(message)


class SubclassWalker(_classWalker):
    def walk_derivatives(self, cls, seen=None):
        if len(inspect.signature(cls.__subclasses__).parameters) != 0:
            return
        if seen is None:
            seen = set()
        pos = 0
        for pos, subcls in enumerate(cls.__subclasses__()):
            if subcls in seen:
                continue
            seen.add(subcls)
            if self.is_blacklisted(subcls):
                continue
            for grand_daddy in self.walk_derivatives(subcls, seen):
                yield grand_daddy
        if pos == 0:
            yield cls


class KlassWalker(_classWalker):
    def walk_derivatives(self, cls, seen=None):
        if len(inspect.signature(cls.__subclasses__).parameters) != 0:
            return

        if seen is None:
            seen = set()
        elif cls not in seen:
            seen.add(cls)
            yield cls

        for subcls in cls.__subclasses__():
            if subcls in seen:
                continue
            for node in self.walk_derivatives(subcls, seen=seen):
                yield node


@deprecated("Use snakeoil.code_quality.Slots instead", removal_in=(0, 12, 0))
class SlotShadowing(TargetedNamespaceWalker, SubclassWalker):
    target_namespace = "snakeoil"
    err_if_slots_is_str = True
    err_if_slots_is_mutable = True
    strict = False

    def recurse_parents(self, kls, seen=None):
        if not seen:
            seen = set()
        for subcls in kls.__bases__:
            if subcls in seen:
                continue
            seen.add(subcls)
            for grand_dad in self.recurse_parents(subcls, seen=seen):
                yield grand_dad
            yield subcls

    @staticmethod
    def mk_name(kls):
        return f"{kls.__module__}.{kls.__name__}"

    def _should_ignore(self, kls):
        return self.mk_name(kls).split(".")[0] != self.target_namespace

    def run_check(self, kls):
        if getattr(kls, "__slotting_intentionally_disabled__", False):
            return

        slotting = {}
        raw_slottings = {}

        for parent in self.recurse_parents(kls):
            slots = getattr(parent, "__slots__", None)

            if slots is None:
                continue

            if isinstance(slots, str):
                slots = (slots,)
            elif isinstance(slots, (dict, list)):
                slots = tuple(slots)

            raw_slottings[slots] = parent
            for slot in slots:
                slotting.setdefault(slot, parent)

        slots = getattr(kls, "__slots__", None)
        if slots is None and not slotting:
            return

        if isinstance(slots, str):
            if self.err_if_slots_is_str:
                self.report_issue(
                    f"cls {kls!r}; slots is {slots!r} (should be a tuple or list)"
                )
            slots = (slots,)

        if slots is None:
            assert not raw_slottings

        if not isinstance(slots, tuple):
            if self.err_if_slots_is_mutable:
                self.report_issue(
                    f"cls {kls!r}; slots is {slots!r}- - should be a tuple"
                )
            slots = tuple(slots)

        if slots is None or (slots and slots in raw_slottings):
            # we do a bool on slots to ignore (); that's completely valid
            # this means that the child either didn't define __slots__, or
            # daftly copied the parents... thus defeating the purpose.
            self.report_issue(
                f"cls {kls!r}; slots is {slots!r}, seemingly inherited from "
                f"{raw_slottings[slots]!r}; the derivative class should be __slots__ = ()"
            )

        for slot in slots:
            if slot in slotting:
                self.report_issue(
                    f"cls {kls!r}; slot {slot!r} was already defined at {slotting[slot]!r}"
                )
