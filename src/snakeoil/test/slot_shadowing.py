import pytest

from . import mixins


class SlotShadowing(mixins.TargetedNamespaceWalker, mixins.SubclassWalker):

    target_namespace = 'snakeoil'
    err_if_slots_is_str = True
    err_if_slots_is_mutable = True

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

    def _should_ignore(self, kls):
        return self.mk_name(kls).split(".")[0] != self.target_namespace

    def run_check(self, kls):
        if getattr(kls, '__slotting_intentionally_disabled__', False):
            return

        slotting = {}
        raw_slottings = {}

        for parent in self.recurse_parents(kls):
            slots = getattr(parent, '__slots__', None)

            if slots is None:
                continue

            if isinstance(slots, str):
                slots = (slots,)
            elif isinstance(slots, dict):
                slots = tuple(slots)

            raw_slottings[slots] = parent
            for slot in slots:
                slotting.setdefault(slot, parent)

        slots = getattr(kls, '__slots__', None)
        if slots is None and not slotting:
            return

        if isinstance(slots, str):
            if self.err_if_slots_is_str:
                pytest.fail(
                    "cls %r; slots is %r (should be a tuple or list)" %
                    (kls, slots))
            slots = (slots,)

        if slots is None:
            assert not raw_slottings

        if not isinstance(slots, tuple):
            if self.err_if_slots_is_mutable:
                pytest.fail(
                    "cls %r; slots is %r- - should be a tuple" % (kls, slots))
            slots = tuple(slots)

        if slots is None or (slots and slots in raw_slottings):
            # we do a bool on slots to ignore (); that's completely valid
            # this means that the child either didn't define __slots__, or
            # daftly copied the parents... thus defeating the purpose.
            pytest.fail(
                "cls %r; slots is %r, seemingly inherited from %r; the "
                "derivative class should be __slots__ = ()" %
                (kls, slots, raw_slottings[slots]))

        for slot in slots:
            if slot in slotting:
                pytest.fail(
                    "cls %r; slot %r was already defined at %r" %
                    (kls, slot, slotting[slot]))
