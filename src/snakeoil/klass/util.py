__all__ = ("get_attrs_of", "get_slots_of", "combine_classes")
import builtins
import functools
from typing import Any, Iterable

_known_builtins = frozenset(
    v for k, v in vars(builtins).items() if not k.startswith("_")
)


def get_slots_of(kls: type) -> Iterable[tuple[type, None | tuple[str, ...]]]:
    """Visit a class MRO collecting all slotting

    This cannot collect slotting of C objects- python builtins like object,
    or literal python C extensions, not unless they expose __slots__.

    """
    yield (kls, getattr(kls, "__slots__", () if kls in _known_builtins else None))
    for base in kls.mro():
        yield (
            base,
            getattr(base, "__slots__", () if base in _known_builtins else None),
        )


def get_attrs_of(
    obj: Any, weakref=False, suppressions: Iterable[str] = (), _sentinel=object()
) -> Iterable[tuple[str, Any]]:
    """
    yield the attributes of a given instance.

    This handles both slotted and non slotted classes- slotted
    classes do not have __dict__.  It also handles mixed derivations,
    a non slotted class that inherited from a slotted class.

    For an ordered __dict__ class, the ordering is *not* honored in what
    this yields.

    :param weakref: by default, suppress that __weakref__ exists since it's
      python internal bookkeeping.  The only reason to enable this is for introspection
      tools; even state saving tools shouldn't care about __weakref__
    :param suppressions: attributes to suppress from the return.  Use this
      as a way to avoid having to write a filter in the consumer- this already
      has to do filtering after all.
    """
    seen = set(suppressions)
    seen.add("__weakref__")
    # if weakref is supported, it's either a ref or None- the attribute always
    # exists however.
    if weakref and (r := getattr(obj, "__weakref__", None)) is not None:
        yield "__weakref__", r
    for k, v in getattr(obj, "__dict__", {}).items():
        if k not in seen:
            yield (k, v)
            seen.add(k)
    for _, slots in get_slots_of(type(obj)):
        if slots is None:
            continue
        for slot in slots:
            if slot not in seen:
                if (o := getattr(obj, slot, _sentinel)) is not _sentinel:
                    yield slot, o
                    seen.add(slot)


@functools.lru_cache
def combine_classes(kls: type, *extra: type) -> type:
    """Given a set of classes, combine this as if one had wrote the class by hand

    This is primarily for composing metaclasses on the fly; this:

    class foo(metaclass=combine_metaclasses(kls1, kls2, kls3)): pass

    is the same as if you did this:

    class mkls(kls1, kls2, kls3): pass
    class foo(metaclass=mkls): pass
    """
    klses = [kls]
    klses.extend(extra)

    if len(klses) == 1:
        return kls

    class combined(*klses):
        pass

    combined.__name__ = f"combined_{'_'.join(kls.__qualname__ for kls in klses)}"
    return combined
