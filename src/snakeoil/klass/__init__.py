"""
common class implementations, and optimizations

The functionality contained within this module is of primary use for building
classes themselves and cutting down on a significant amount of boilerplate
involved in writing classes.
"""

__all__ = (
    "abstractclassvar",
    "combine_metaclasses",
    "generic_equality",
    "reflective_hash",
    "inject_richcmp_methods_from_cmp",
    "static_attrgetter",
    "jit_attr",
    "jit_attr_none",
    "jit_attr_named",
    "jit_attr_ext_method",
    "alias_attr",
    "cached_hash",
    "cached_property",
    "cached_property_named",
    "copy_docs",
    "steal_docs",
    "is_metaclass",
    "ImmutableInstance",
    "immutable_instance",
    "inject_immutable_instance",
    "alias_method",
    "SlotsPicklingMixin",
    "DirProxy",
    "GetAttrProxy",
    "get_attrs_of",
    "get_slot_of",
    "get_slots_of",
    "get_subclasses_of",
)

import abc
import inspect
import typing
from collections import deque
from operator import attrgetter

from snakeoil._internals import deprecated
from snakeoil.sequences import unique_stable

from ..caching import WeakInstMeta
from ._deprecated import (
    ImmutableInstance,
    immutable_instance,
    inject_immutable_instance,
    inject_richcmp_methods_from_cmp,
    steal_docs,
)
from .properties import (
    _uncached_singleton,  # noqa: F401 .  This exists purely due to a stupid usage of pkgcore.ebuild.profile which is being removed.
    alias_attr,
    alias_method,
    cached_property,
    cached_property_named,
    jit_attr,
    jit_attr_ext_method,
    jit_attr_named,
    jit_attr_none,
)
from .util import (
    combine_metaclasses,
    copy_docs,
    get_attrs_of,
    get_slot_of,
    get_slots_of,
    get_subclasses_of,
    is_metaclass,
)

sentinel = object()

T = typing.TypeVar("T")


def GetAttrProxy(target):
    def reflected_getattr(self, attr):
        return getattr(object.__getattribute__(self, target), attr)

    return reflected_getattr


def DirProxy(target):
    def combined_dir(obj):
        attrs = dir(getattr(obj, target))
        try:
            attrs.extend(obj.__dict__)
        except AttributeError:
            attrs.extend(obj.__slots__)
        return sorted(set(attrs))

    return combined_dir


def contains(self, key):
    """
    return True if key is in self, False otherwise
    """
    try:
        # pylint: disable=pointless-statement
        self[key]
        return True
    except KeyError:
        return False


def get(self, key, default=None):
    """
    return ``default`` if ``key`` is not in self, else the value associated with ``key``
    """
    try:
        return self[key]
    except KeyError:
        return default


def reflective_hash(attr):
    """
    default __hash__ implementation that returns a pregenerated hash attribute

    :param attr: attribute name to pull the hash from on the instance
    :return: hash value for instance this func is used in.
    """

    def __hash__(self):
        return getattr(self, attr)

    return __hash__


class _abstractclassvar:
    __slots__ = ()
    __isabstractmethod__ = True


def abstractclassvar(_: type[T]) -> T:
    """
    mechanism to use with ClassVars to force abc.ABC to block creation if the subclass hasn't set it.

    This can be used like thus:
    >>> from typing import ClassVar
    >>> class foon(abc.ABC):
    ...     required_class_var: ClassVar[str] = abstractclassvar(str)
    ...
    >>>
    >>> foon()
    Traceback (most recent call last):
        File "<python-input-8>", line 1, in <module>
        foon()
        ~~~~^^
    TypeError: Can't instantiate abstract class foon without an implementation for abstract method 'required_class_var'

    The error message implies a method when it's not, but that  is a limitation of abc.ABC.  The point of this is to allow forcing that derivatives create
    the cvar, thus the trade off.

    The mechanism currently is janky; you must pass in the type definition since it's the
    only way to attach this information to the returned object, lieing to the type system
    that the value is type compatible while carrying the marker abc.ABC needs.
    """
    return typing.cast(T, _abstractclassvar())


class GenericEquality(abc.ABC):
    """
    implement simple __eq__/__ne__ comparison via a list of attributes to compare

    For deriviatives, __attr_comparison__ must be defined; this is a sequence of attributes
    to check for comparison.

    If you need to extend the logic beyond just adding an attribute, override __eq__; __ne__
    is just a negated reflection of that methods result.

    >>> from snakeoil.klass import GenericEquality
    >>> class kls(GenericEquality):
    ...   __attr_comparison__ = ("a", "b", "c")
    ...   def __init__(self, a=1, b=2, c=3):
    ...     self.a, self.b, self.c = a, b, c
    >>>
    >>> assert kls() == foo()
    >>> assert foo(3, 2, 1) != foo()

    :cvar __attr_comparison__: tuple[str,...] that is the ordered sequence of comparison to perform.  For performance you should order this as the attributes
    with the highest cardinality and cheap comparisons.
    """

    __slots__ = ()

    __attr_comparison__: typing.ClassVar[tuple[str, ...]] = abstractclassvar(
        tuple[str, ...]
    )

    __attr_comparison__: typing.ClassVar[tuple[str, ...]]

    def __eq__(
        self, value, /, attr_comparison_override: tuple[str, ...] | None = None
    ) -> bool:
        """
        Comparison is down via comparing attributes listed in self.__attr_comparison__,
        or via the passed in attr_comparison_override.  That exists specifically to
        simplify subclass partial reuse of the class when logic gets complex.
        """
        if self is value:
            return True
        for attr in (
            self.__attr_comparison__
            if attr_comparison_override is None
            else attr_comparison_override
        ):
            if getattr(self, attr, sentinel) != getattr(value, attr, sentinel):
                return False
        return True

    def __init_subclass__(cls, compare_slots=False, **kwargs) -> None:
        slotting = list(get_slots_of(cls))
        if compare_slots:
            if "__attr_comparison__" in cls.__dict__:
                raise TypeError(
                    "compare_slots=True makes no sense when __attr_comparison__ is explicitly set in the class directly"
                )

            all_slots = []
            for slot in slotting:
                if slot.slots is None:
                    raise TypeError(
                        f"compare_slots cannot be used: MRO chain has class {slot.cls} which lacks slotting.  Set __attr_comparison__ manually"
                    )
                all_slots.extend(slot.slots)
            cls.__attr_comparison__ = tuple(unique_stable(all_slots))
            return super().__init_subclass__(**kwargs)

        if inspect.isabstract(cls):
            return super().__init_subclass__(**kwargs)

        elif not isinstance(cls.__attr_comparison__, (tuple, property)):
            raise TypeError(
                f"__attr_comparison__ must be a tuple, received {cls.__attr_comparison__!r}"
            )
        return super().__init_subclass__(**kwargs)


class GenericRichComparison(GenericEquality):
    __slots__ = ()

    def __lt__(self, value, attr_comparison_override: tuple[str, ...] | None = None):
        if self is value:
            return False
        attrlist = (
            self.__attr_comparison__
            if attr_comparison_override is None
            else attr_comparison_override
        )
        for attr in attrlist:
            obj1, obj2 = getattr(self, attr, sentinel), getattr(value, attr, sentinel)
            if obj1 is sentinel:
                if obj2 is sentinel:
                    continue
                return True
            elif obj2 is sentinel:
                return False
            if not (obj1 >= obj2):  # pyright: ignore[reportOperatorIssue]
                return True
        return False

    def __le__(self, value, attr_comparison_override: tuple[str, ...] | None = None):
        if self is value:
            return True
        attrlist = (
            self.__attr_comparison__
            if attr_comparison_override is None
            else attr_comparison_override
        )
        for attr in attrlist:
            obj1, obj2 = getattr(self, attr, sentinel), getattr(value, attr, sentinel)
            if obj1 is sentinel:
                if obj2 is sentinel:
                    continue
                return True
            elif obj2 is sentinel:
                return False
            if not (obj1 > obj2):  # pyright: ignore[reportOperatorIssue]
                return True
        return False

    def __gt__(self, value, attr_comparison_override: tuple[str, ...] | None = None):
        return not self.__le__(value, attr_comparison_override=attr_comparison_override)

    def __ge__(self, value, attr_comparison_override: tuple[str, ...] | None = None):
        return not self.__lt__(value, attr_comparison_override=attr_comparison_override)


@deprecated(
    "inherit from snakeoil.klass.GenericEquality instead",
    removal_in=(0, 12, 0),
)
def generic_equality(
    name,
    bases,
    scope,
    real_type=type,
    eq=GenericEquality.__eq__,
    ne=lambda self, other: not GenericEquality.__eq__(self, other),
):
    """
    Deprecated.  Use snakeoil.klass.GenericEquality instead.

    metaclass generating __eq__/__ne__ methods from an attribute list

    The consuming class is abstract until a layer sets a class attribute
    named `__attr_comparison__` which is the list of attributes to compare.

    This can optionally derived via passing `compare_slots=True` in the class
    creation.

    :raise: TypeError if __attr_comparison__ is incorrectly defined

    >>> from snakeoil.klass import generic_equality
    >>> class foo(metaclass=generic_equality):
    ...   __attr_comparison__ = ("a", "b", "c")
    ...   def __init__(self, a=1, b=2, c=3):
    ...     self.a, self.b, self.c = a, b, c
    >>>
    >>> assert foo() == foo()
    >>> assert not (foo() != foo())
    >>> assert foo(1,2,3) == foo()
    >>> assert foo(3, 2, 1) != foo()
    """
    attrlist = scope.pop("__attr_comparison__", None)
    if attrlist is None:
        raise TypeError("__attr_comparison__ must be in the classes scope")
    elif isinstance(attrlist, str) or not all(isinstance(x, str) for x in attrlist):
        raise TypeError(
            "__attr_comparison__ must be a sequence of strings, got {attrlist!r}"
        )

    scope["__attr_comparison__"] = tuple(attrlist)
    scope.setdefault("__eq__", GenericEquality.__eq__)
    scope.setdefault("__ne__", GenericEquality.__ne__)
    return real_type(name, bases, scope)


@deprecated(
    "Use operator.attrgetter instead",
    removal_in=(0, 12, 0),
)
class chained_getter(
    GenericEquality, metaclass=combine_metaclasses(WeakInstMeta, abc.ABCMeta)
):
    """
    Deprecated.  Use operator.attrgetter instead.
    """

    __slots__ = ("namespace", "getter")
    __fifo_cache__ = deque()
    __inst_caching__ = True
    __attr_comparison__ = ("namespace",)

    def __init__(self, namespace):
        """
        :param namespace: python namespace path to try and resolve on target objects
        """
        self.namespace = namespace
        self.getter = attrgetter(namespace)
        if len(self.__fifo_cache__) > 10:
            self.__fifo_cache__.popleft()
        self.__fifo_cache__.append(self)

    def __hash__(self):
        # XXX shouldn't this hash to self.__class__ in addition?
        # via the __eq__, it won't invalidly be the same, but still..
        return hash(self.namespace)

    def __call__(self, obj):
        return self.getter(obj)


static_attrgetter = deprecated(
    "Use operator.attrgetter instead",
    removal_in=(0, 12, 0),
)(chained_getter)


def cached_hash(func):
    """
    decorator to cache the hash value.

    It's important to note that you should only be caching the hash value
    if you know it cannot change.

    >>> from snakeoil.klass import cached_hash
    >>> class foo:
    ...   def __init__(self):
    ...     self.hash_invocations = 0
    ...
    ...   @cached_hash
    ...   def __hash__(self):
    ...     self.hash_invocations += 1
    ...     return 12345
    >>>
    >>> f = foo()
    >>> assert f.hash_invocations == 0
    >>> assert hash(f) == 12345
    >>> assert f.hash_invocations == 1
    >>> assert hash(f) == 12345        # note we still get the same value
    >>> assert f.hash_invocations == 1 # and that the function was invoked only once.
    """

    def __hash__(self):
        val = getattr(self, "_hash", None)
        if val is None:
            object.__setattr__(self, "_hash", val := func(self))
        return val

    return __hash__


class SlotsPicklingMixin:
    """Default pickling support for classes that use __slots__."""

    __slots__ = ()

    def __getstate__(self):
        return dict(get_attrs_of(self))

    def __setstate__(self, state):
        for k, v in state.items():
            object.__setattr__(self, k, v)
