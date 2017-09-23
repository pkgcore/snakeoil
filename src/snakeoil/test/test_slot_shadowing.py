# Copyright: 2009-2011 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD

from snakeoil.test import mixins, TestCase


class Test_slot_shadowing(mixins.TargetedNamespaceWalker, mixins.SubclassWalker,
                          TestCase):

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
                raise self.failureException(
                    "cls %r; slots is %r (should be a tuple or list)" %
                    (kls, slots))
            slots = (slots,)

        if slots is None:
            assert not raw_slottings

        if not isinstance(slots, tuple):
            if self.err_if_slots_is_mutable:
                raise self.failureException(
                    "cls %r; slots is %r- - should be a tuple" % (kls, slots))
            slots = tuple(slots)

        if slots is None or (slots and slots in raw_slottings):
            # we do a bool on slots to ignore (); that's completely valid
            # this means that the child either didn't define __slots__, or
            # daftly copied the parents... thus defeating the purpose.
            raise self.failureException(
                "cls %r; slots is %r, seemingly inherited from %r; the "
                "derivative class should be __slots__ = ()" %
                (kls, slots, raw_slottings[slots]))

        for slot in slots:
            if slot in slotting:
                raise self.failureException(
                    "cls %r; slot %r was already defined at %r" %
                    (kls, slot, slotting[slot]))
