__all__ = (
    "get_attrs_of",
    "get_instances_of",
    "get_slot_of",
    "get_slots_of",
    "get_subclasses_of",
    "is_metaclass",
    "combine_metaclasses",
    "copy_class_docs",
    "copy_docs",
    "ClassSlotting",
)

import builtins
import functools
import gc
import inspect
import types
import typing

_known_builtins = frozenset(
    v for k, v in vars(builtins).items() if not k.startswith("_")
)


class ClassSlotting(typing.NamedTuple):
    cls: type
    slots: typing.Sequence[str] | None


def get_slots_of(kls: type) -> typing.Iterable[ClassSlotting]:
    """Visit a class MRO collecting all slotting

    This cannot collect slotting of C objects- python builtins like object,
    or literal python C extensions, not unless they expose __slots__.

    """
    for base in kls.mro():
        yield get_slot_of(base)


def get_slot_of(cls: type) -> ClassSlotting:
    """Return the non-inherited slotting from a class, IE specifically what that definition set."""
    return ClassSlotting(
        cls,
        # class objects provide a proxy map so abuse that to look at the class
        # directly.
        cls.__dict__.get("__slots__", () if cls in _known_builtins else None),
    )


def get_attrs_of(
    obj: typing.Any,
    weakref=False,
    suppressions: typing.Iterable[str] = (),
    _sentinel=object(),
) -> typing.Iterable[tuple[str, typing.Any]]:
    """
    A version of `vars()` that actually returns slotted attributes.  Use this instead of `vars()`.

    This handles both slotted and non slotted classes.  `vars()` only returns what is in `__dict__`,
    it will *not* return any slotted attributed.  This will return both.

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
    for data in get_slots_of(type(obj)):
        if data.slots is None:
            continue
        for slot in data.slots:
            if slot not in seen:
                if (o := getattr(obj, slot, _sentinel)) is not _sentinel:
                    yield slot, o
                    seen.add(slot)


def is_metaclass(cls: type) -> typing.TypeGuard[type[type]]:
    """discern if something is a metaclass.  This intentionally ignores function based metaclasses"""
    return issubclass(cls, type)


def get_subclasses_of(
    cls: type,
    only_leaf_nodes=False,
    ABC: None | bool = None,
) -> typing.Iterable[type]:
    """yield the subclasses of the given class.

    This walks the in memory tree of a class hierarchy, yield the subclasses of the given
    cls after optional filtering.

    Note: this cannot work on metaclasses.  Python doesn't carry the necessary bookkeeping.
    The first level of a metaclass will be returned, but none of it's derivative, and it'll
    be treated as a leaf node- even if it isn't.

    :param only_leaf_nodes: if True, only yield classes which have no subclasses
    :param ABC: if True, only yield abstract classes.  If False, only yield classes no longer
      abstract.  If None- the default- do no filtering for ABC.
    """
    if is_metaclass(cls):
        return
    seen = set()
    stack = cls.__subclasses__()
    while stack:
        current = stack.pop()
        if (
            current in seen
        ):  # diamond inheritance can lead to seeing the same leaft multiple times.
            continue
        seen.add(current)

        subclasses = () if is_metaclass(current) else current.__subclasses__()
        stack.extend(subclasses)

        if ABC is not None:
            if inspect.isabstract(current) != ABC:
                continue

        if not only_leaf_nodes:
            yield current
        elif not subclasses:  # it's a leaf
            yield current


def get_instances_of(cls: type, getattribute=False) -> list[type]:
    """
    Find all instances of the class in memory that are reachable by python GC.

    Certain cpython types may not implement visitation correctly- they're broke,
    but they will hide the instances from this.  This should never happen, but
    if you know an instance exists and is in cpython object, this is the 'why'

    Note: this uses object.__getattribute__ directly.  Even if your instance has
    a __getattribute__ that returns a __class__ that isn't it's actuall class, this
    *will* find it.
    """
    return [
        x
        for x in gc.get_referrers(cls)
        # __getattribute__ because certain thunking implementations also lie as
        # what class they are- they proxy in a way they appear as their target.
        if object.__getattribute__(x, "__class__") is cls
    ]


@functools.lru_cache
def combine_metaclasses(kls: type, *extra: type) -> type:
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


# For this list, look at functools.wraps for an idea of what is possibly mappable.
_copy_doc_targets = ("__annotations__", "__doc__", "__type_params__")


def copy_docs(target):
    """Copy the docs and annotations off of the given target

    This is used for implementations that look like something (the target), but
    do not actually invoke the the target.

    If you're just wrapping something- a true decorator- use functools.wraps
    """

    if isinstance(target, type):
        return copy_class_docs(target)

    def inner(functor):
        for name in _copy_doc_targets:
            try:
                setattr(functor, name, getattr(target, name))
            except AttributeError:
                pass
        return functor

    return inner


def copy_class_docs(source_class):
    """
    Copy the docs and annotations of a target class for methods that intersect with the target.

    This does *not* check that the prototype signatures are the same, and it exempts __init__
    since that makes no sense to copy
    """

    def do_it(cls):
        for name in set(source_class.__dict__).intersection(cls.__dict__):
            obj = getattr(cls, name)
            if not isinstance(obj, types.FunctionType):
                continue
            if getattr(obj, "__annotations__", None) or getattr(obj, "__doc__", None):
                continue
            setattr(cls, name, copy_docs(getattr(source_class, name))(obj))
        return cls

    return do_it
