"""Implementations of immutable instance metaclasses"""

__all__ = ("immutable_instance", "inject_immutable_instance", "ImmutableInstance")

import inspect
import typing

from snakeoil._internals import deprecated


@deprecated(
    "Use snakeoil.klass.meta.Immutable* metaclasses instead",
    qualname="snakeoil.klass.immutable_instance",
)
def immutable_instance(
    name: str, bases: tuple[type], scope: dict[str, typing.Any], real_type=type
) -> type:
    """metaclass that makes instances of this class effectively immutable

    It still is possible to do object.__setattr__ to get around it during
    initialization, but usage of this class effectively prevents accidental
    modification, instead requiring explicit modification."""
    with deprecated.suppress_deprecations():
        inject_immutable_instance(scope)
    return real_type(name, bases, scope)


@deprecated(
    "Use snakeoil.klass.meta.Immutable* metaclasses instead",
    removal_in=(0, 12, 0),
    qualname="snakeoil.klass.ImmutableInstance*",
)
class ImmutableInstance:
    """Class that disables surface-level attribute modifications."""

    def __setattr__(self, attr, _value):
        raise AttributeError(self, attr)

    def __delattr__(self, attr):
        raise AttributeError(self, attr)

    def __getstate__(self) -> dict[str, typing.Any]:
        return self.__dict__.copy()

    def __setstate__(self, state) -> None:
        # This is necessary since any mutation attempts would explode.
        for k, v in state.items():
            object.__setattr__(self, k, v)


@deprecated(
    "Use snakeoil.klass.meta.Immutable* metaclasses instead",
    removal_in=(0, 12, 0),
    qualname="snakeoil.klass.inject_immutable_instance",
)
def inject_immutable_instance(scope: dict[str, typing.Any]):
    """inject immutable __setattr__ and __delattr__ implementations

    see immutable_instance for further details

    :param scope: mapping to modify, inserting __setattr__ and __delattr__
      methods if they're not yet defined.
    """
    scope.setdefault("__setattr__", ImmutableInstance.__setattr__)
    scope.setdefault("__delattr__", ImmutableInstance.__delattr__)


def __generic_lt(self, other):
    """generic implementation of __lt__ that uses __cmp__"""
    return self.__cmp__(other) < 0


def __generic_le(self, other):
    """reflective implementation of __le__ that uses __cmp__"""
    return self.__cmp__(other) <= 0


def __generic_eq(self, other):
    """reflective implementation of __eq__ that uses __cmp__"""
    return self.__cmp__(other) == 0


def __generic_ne(self, other):
    """reflective implementation of __ne__ that uses __cmp__"""
    return self.__cmp__(other) != 0


def __generic_ge(self, other):
    """reflective implementation of __ge__ that uses __cmp__"""
    return self.__cmp__(other) >= 0


def __generic_gt(self, other):
    """reflective implementation of __gt__ that uses __cmp__"""
    return self.__cmp__(other) > 0


@deprecated(
    "Use functools.total_ordering instead",
    removal_in=(0, 12, 0),
    qualname="snakeoil.klass.inject_richcmp_methods_from_cmp",
)
def inject_richcmp_methods_from_cmp(scope):
    """
    class namespace modifier injecting richcmp methods that rely on __cmp__ for py3k
    compatibility

    Note that this just injects generic implementations such as :py:func:`__generic_lt`;
    if a method already exists, it will not override it.  This behavior is primarily
    beneficial if the developer wants to optimize one specific method- __lt__ for sorting
    reasons for example, but performance is less of a concern for the other
    rich comparison methods.

    Example usage:

    >>> from snakeoil.klass import inject_richcmp_methods_from_cmp
    >>> from snakeoil.compatibility import cmp
    >>> class foo:
    ...
    ...   # note that for this example, we inject always since we're
    ...   # explicitly accessing __ge__ methods- under py2k, they wouldn't
    ...   # exist (__cmp__ would be sufficient).
    ...
    ...   # add the generic rich comparsion methods to the local class namespace
    ...   inject_richcmp_methods_from_cmp(locals())
    ...
    ...   def __init__(self, a, b):
    ...     self.a, self.b = a, b
    ...
    ...   def __cmp__(self, other):
    ...     c = cmp(self.a, other.a)
    ...     if c == 0:
    ...       c = cmp(self.b, other.b)
    ...     return c
    >>>
    >>> assert foo(1, 2).__ge__(foo(1, 1))
    >>> assert foo(1, 1).__eq__(foo(1, 1))

    :param scope: the modifiable scope of a class namespace to work on
    """

    for key, func in (
        ("__lt__", __generic_lt),
        ("__le__", __generic_le),
        ("__eq__", __generic_eq),
        ("__ne__", __generic_ne),
        ("__ge__", __generic_ge),
        ("__gt__", __generic_gt),
    ):
        scope.setdefault(key, func)


@deprecated(
    "Use functools.wraps",
    removal_in=(0, 12, 0),
    qualname="snakeoil.klass.steal_docs",
)
def steal_docs(target, ignore_missing=False, name=None):
    """
        decorator to steal __doc__ off of a target class or function

        Specifically when the target is a class, it will look for a member matching
        the functors names from target, and clones those docs to that functor;
        otherwise, it will simply clone the targeted function's docs to the
        functor.

        :param target: class or function to steal docs from
        :param ignore_missing: if True, it'll swallow the exception if it
            cannot find a matching method on the target_class.  This is rarely
            what you want- it's mainly useful for cases like `dict.has_key`, where it
            exists in py2k but doesn't in py3k
        :param name: function name from class to steal docs from, by default the name of the
            decorated function is used; only used when the target is a class name

        Example Usage:

        >>> from snakeoil.klass import steal_docs
    >>> class foo(list):
        ...   @steal_docs(list)
        ...   def extend(self, *a):
        ...     pass
        >>>
        >>> f = foo([1,2,3])
        >>> assert f.extend.__doc__ == list.extend.__doc__
    """

    def inner(functor):
        if inspect.isclass(target):
            if name is not None:
                target_name = name
            else:
                target_name = functor.__name__
            try:
                obj = getattr(target, target_name)
            except AttributeError:
                if not ignore_missing:
                    raise
                return functor
        else:
            obj = target
        functor.__doc__ = obj.__doc__
        return functor

    return inner
