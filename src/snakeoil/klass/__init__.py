"""
common class implementations, and optimizations

The functionality contained within this module is of primary use for building
classes themselves and cutting down on a significant amount of boilerplate
involved in writing classes.
"""

__all__ = (
    "combine_classes",
    "generic_equality",
    "reflective_hash",
    "inject_richcmp_methods_from_cmp",
    "static_attrgetter",
    "instance_attrgetter",
    "jit_attr",
    "jit_attr_none",
    "jit_attr_named",
    "jit_attr_ext_method",
    "alias_attr",
    "cached_hash",
    "cached_property",
    "cached_property_named",
    "steal_docs",
    "ImmutableInstance",
    "immutable_instance",
    "inject_immutable_instance",
    "alias_method",
    "aliased",
    "alias",
    "patch",
    "SlotsPicklingMixin",
    "DirProxy",
    "GetAttrProxy",
    "get_slots_of",
    "get_attrs_of",
)

import abc
import inspect
from collections import deque
from functools import wraps
from importlib import import_module
from operator import attrgetter
from typing import Any

from snakeoil.deprecation import deprecated as warn_deprecated

from ..caching import WeakInstMeta
from .deprecated import (
    ImmutableInstance,
    immutable_instance,
    inject_immutable_instance,
    inject_richcmp_methods_from_cmp,
)
from .properties import (
    _uncached_singleton,  # noqa: F401 .  This exists purely due to a stupid usage of pkgcore.ebuild.profile which is being removed.
    alias,
    alias_attr,
    alias_method,
    aliased,
    cached_property,
    cached_property_named,
    jit_attr,
    jit_attr_ext_method,
    jit_attr_named,
    jit_attr_none,
)
from .util import combine_classes, get_attrs_of, get_slots_of

sentinel = object()


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
    """

    __slots__ = ()

    # The pyright disable is since we're shoving in annotations in a weird way.
    # ABC is used to ensure this gets changed, but the actual class value in the non virtual
    # class must be tuple.
    @property
    @abc.abstractmethod
    def __attr_comparison__(self) -> tuple[str, ...]:  # pyright: ignore[reportRedeclaration]
        """list of attributes to compare.

        This should be replaced with a tuple in derivative classes unless dynamic
        behavior is needed for discerning what attributes to compare.

        The only reason to do this is if you're inheriting from something that is GenericEquality,
        and you fully have overridden the comparison logic and wish to document for any
        consumers __attr_comparison__ is no longer relevant.
        """
        pass

    __attr_comparison__: tuple[str, ...]

    def __eq__(self, other: Any) -> bool:
        """
        Comparison is down via comparing attributes listed in self.__attr_comparison__
        """
        if self is other:
            return True
        for attr in self.__attr_comparison__:
            if getattr(self, attr, sentinel) != getattr(other, attr, sentinel):
                return False
        return True

    def __init_subclass__(cls) -> None:
        if cls.__attr_comparison__ is None:
            # __ne__ is just a reflection of __eq__, so just check that one.
            if cls.__eq__ is GenericEquality.__eq__:
                raise TypeError(
                    "__attr_comparison__ was set to None, but __eq__ is still GenericEquality.__eq__"
                )
            # If this is the first disabling, update the annotations
            if "__attr_comparison__" in cls.__dict__:
                cls.__annotations__["__attr_comparison__"] = None
        elif not isinstance(cls.__attr_comparison__, (tuple, property)):
            raise TypeError(
                f"__attr_comparison__ must be a tuple, received {cls.__attr_comparison__!r}"
            )
        return super().__init_subclass__()


@warn_deprecated(
    "generic_equality metaclass usage is deprecated; inherit from snakeoil.klass.GenericEquality instead."
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

    The consuming class must set a class attribute named __attr_comparison__
    that is a sequence that lists the attributes to compare in determining
    equality or a string naming the class attribute to pull the list of
    attributes from (e.g. '__slots__').

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


@warn_deprecated(
    "snakeoil.klass.chained_getter is deprecated.  Use operator.attrgetter instead."
)
class chained_getter(
    GenericEquality, metaclass=combine_classes(WeakInstMeta, abc.ABCMeta)
):
    """
    Deprecated.  Use operator.attrgetter instead.

    object that will do multi part lookup, regardless of if it's in the context
    of an instancemethod or staticmethod.

    Note that developers should use :py:func:`static_attrgetter` or
    :py:func:`instance_attrgetter` instead of this class directly.  They should do
    this since dependent on the python version, there may be a faster implementation
    to use- for python2.6, :py:func:`operator.attrgetter` can do this same functionality
    but cannot be used as an instance method (like most stdlib functions, it's a staticmethod)

    Example Usage:

    >>> from snakeoil.klass import chained_getter
    >>> # general usage example: basically like operator.attrgetter
    >>> print(chained_getter("extend")(list).__name__)
    extend
    >>>
    >>> class foo:
    ...
    ...   seq = (1,2,3)
    ...
    ...   def __init__(self, a=1):
    ...     self.a = a
    ...
    ...   b = property(chained_getter("a"))
    ...   # please note that recursive should be using :py:func:`alias_attr` instead,
    ...   # since that's effectively what that functor does
    ...   recursive = property(chained_getter("seq.__hash__"))
    >>>
    >>> o = foo()
    >>> print(o.a)
    1
    >>> print(o.b)
    1
    >>> print(o.recursive == foo.seq.__hash__)
    True
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


static_attrgetter = warn_deprecated(
    "snakeoil.klass.static_attrgetter is deprecated.  Use operator.attrgetter instead"
)(chained_getter)
instance_attrgetter = chained_getter


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


def patch(target, external_decorator=None):
    """Simplified monkeypatching via decorator.

    :param target: target method to replace
    :param external_decorator: decorator used on target method,
        e.g. classmethod or staticmethod

    Example usage (that's entirely useless):

    >>> import math
    >>> from snakeoil.klass import patch
    >>> @patch('math.ceil')
    >>> def ceil(orig_ceil, n):
    ...   return math.floor(n)
    >>> assert math.ceil(0.1) == 0
    """

    def _import_module(target):
        components = target.split(".")
        import_path = components.pop(0)
        module = import_module(import_path)
        for comp in components:
            try:
                module = getattr(module, comp)
            except AttributeError:
                import_path += f".{comp}"
                module = import_module(import_path)
        return module

    def _get_target(target):
        try:
            module, attr = target.rsplit(".", 1)
        except (TypeError, ValueError):
            raise TypeError(f"invalid target: {target!r}")
        module = _import_module(module)
        return module, attr

    def decorator(func):
        # use the original function wrapper
        func = getattr(func, "_func", func)

        module, attr = _get_target(target)
        orig_func = getattr(module, attr)

        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(orig_func, *args, **kwargs)

        # save the original function wrapper
        wrapper._func = func

        if external_decorator is not None:
            wrapper = external_decorator(wrapper)

        # overwrite the original method with our wrapper
        setattr(module, attr, wrapper)
        return wrapper

    return decorator


class SlotsPicklingMixin:
    """Default pickling support for classes that use __slots__."""

    __slots__ = ()

    def __getstate__(self):
        return dict(get_attrs_of(self))

    def __setstate__(self, state):
        for k, v in state.items():
            object.__setattr__(self, k, v)
