# Copyright: 2009 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD

from snakeoil.test import mixins, TestCase, test_demandload_usage
from snakeoil.compatibility import any
import inspect

class Test_slot_shadowing(mixins.SubclassWalker, mixins.PythonNamespaceWalker,
    TestCase):

    target_namespace = 'snakeoil'
    module_blacklist = test_demandload_usage.TestDemandLoadTargets.module_blacklist
    err_if_slots_is_str = True
    err_if_slots_is_mutable = True

    def load_namespaces(self, namespace=None):
        if namespace is None:
            namespace = self.target_namespace
        for mod in self.walk_namespace(namespace):
            pass

    def test_object_derivatives(self):
        # first load all namespaces...
        self.load_namespaces()

        # next walk all derivatives of object
        for cls in self.walk_derivatives(object):
            self.check_slotting(cls)

    def test_builtin_derivatives(self):
        self.load_namespaces()
        for attr in dir(__builtins__):
            obj = getattr(__builtins__, attr)
            if not inspect.isclass(obj):
                continue
            for cls in self.walk_derivatives(obj):
                self.check_slotting(cls)

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
        return '%s.%s' % (kls.__module__, kls.__name__)

    def _should_check_cls(self, kls):
        return self.mk_name(kls).split(".")[0] == self.target_namespace

    def check_slotting(self, kls):
        # note we ignore diamond mro slotting...
        if not self._should_check_cls(kls):
            return

        if getattr(kls, '__slotting_intentionally_disabled__', False):
            return

        slotting = {}
        raw_slottings = {}

        for parent in self.recurse_parents(kls):
            slots = getattr(parent, '__slots__', None)

            if slots is None:
                continue

            if isinstance(slots, str) or isinstance(slots, unicode):
                slots = (slots,)

            raw_slottings[slots] = parent
            for slot in slots:
                slotting.setdefault(slot, parent)

        slots = getattr(kls, '__slots__', None)
        if slots is None and not slotting:
            return

        if isinstance(slots, str) or isinstance(slots, unicode):
            if self.err_if_slots_is_str:
                raise self.failureException("cls %r; slots is %r "
                    "(should be a tuple or list)" % (kls, slots))
            slots = (slots,)

        if slots is None:
            assert not raw_slottings

        if not isinstance(slots, tuple):
            if self.err_if_slots_is_mutable:
                raise self.failureException("cls %r; slots is %r- "
                    "- should be a tuple" % (kls, slots))
            slots = tuple(slots)


        if slots is None or (slots and slots in raw_slottings):
            # we do a bool on slots to ignore (); that's completely valid
            # this means that the child either didn't define __slots__, or
            # daftly copied the parents... thus defeating the purpose.
            raise self.failureException("cls %r; slots is %r, seemingly "
                "inherited from %r- should be __slots__ = ()" %
                (kls, slots, raw_slottings[slots]))

        for slot in slots:
            if slot in slotting:
                raise self.failureException(
                    "cls %r; slot %r was already defined at %r" %
                    (kls, slot, slotting[slot]))
