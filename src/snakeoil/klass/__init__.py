"""
common class implementations, and optimizations

The functionality contained within this module is of primary use for building
classes themselves and cutting down on a significant amount of boilerplate
involved in writing classes.
"""

__all__ = (
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

import inspect
from collections import deque
from functools import partial, wraps
from importlib import import_module
from operator import attrgetter

from snakeoil._util import deprecated

from ..caching import WeakInstMeta
from .immutable import (
    ImmutableInstance,
    immutable_instance,
    inject_immutable_instance,
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
from .util import get_attrs_of, get_slots_of

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


_attrlist_getter = attrgetter("__attr_comparison__")


def generic_attr_eq(inst1, inst2):
    """
    compare inst1 to inst2, returning True if equal, False if not.

    Comparison is down via comparing attributes listed in inst1.__attr_comparison__
    """
    if inst1 is inst2:
        return True
    for attr in _attrlist_getter(inst1):
        if getattr(inst1, attr, sentinel) != getattr(inst2, attr, sentinel):
            return False
    return True


def generic_attr_ne(inst1, inst2):
    """
    compare inst1 to inst2, returning True if different, False if equal.

    Comparison is down via comparing attributes listed in inst1.__attr_comparison__
    """
    if inst1 is inst2:
        return False
    for attr in _attrlist_getter(inst1):
        if getattr(inst1, attr, sentinel) != getattr(inst2, attr, sentinel):
            return True
    return False


def reflective_hash(attr):
    """
    default __hash__ implementation that returns a pregenerated hash attribute

    :param attr: attribute name to pull the hash from on the instance
    :return: hash value for instance this func is used in.
    """

    def __hash__(self):
        return getattr(self, attr)

    return __hash__


def generic_equality(
    name, bases, scope, real_type=type, eq=generic_attr_eq, ne=generic_attr_ne
):
    """
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
    elif isinstance(attrlist, str):
        attrlist = scope[attrlist]
    for x in attrlist:
        if not isinstance(x, str):
            raise TypeError(
                f"all members of attrlist must be strings- got {type(x)!r} {x!r}"
            )

    scope["__attr_comparison__"] = tuple(attrlist)
    scope.setdefault("__eq__", eq)
    scope.setdefault("__ne__", ne)
    return real_type(name, bases, scope)


def generic_lt(self, other):
    """generic implementation of __lt__ that uses __cmp__"""
    return self.__cmp__(other) < 0


def generic_le(self, other):
    """reflective implementation of __le__ that uses __cmp__"""
    return self.__cmp__(other) <= 0


def generic_eq(self, other):
    """reflective implementation of __eq__ that uses __cmp__"""
    return self.__cmp__(other) == 0


def generic_ne(self, other):
    """reflective implementation of __ne__ that uses __cmp__"""
    return self.__cmp__(other) != 0


def generic_ge(self, other):
    """reflective implementation of __ge__ that uses __cmp__"""
    return self.__cmp__(other) >= 0


def generic_gt(self, other):
    """reflective implementation of __gt__ that uses __cmp__"""
    return self.__cmp__(other) > 0


def inject_richcmp_methods_from_cmp(scope):
    """
    class namespace modifier injecting richcmp methods that rely on __cmp__ for py3k
    compatibility

    Note that this just injects generic implementations such as :py:func:`generic_lt`;
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
        ("__lt__", generic_lt),
        ("__le__", generic_le),
        ("__eq__", generic_eq),
        ("__ne__", generic_ne),
        ("__ge__", generic_ge),
        ("__gt__", generic_gt),
    ):
        scope.setdefault(key, func)


@deprecated(
    "snakeoil.klass.chained_getter is deprecated.  Use operator.attrgetter instead."
)
class chained_getter(metaclass=partial(generic_equality, real_type=WeakInstMeta)):
    """
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


static_attrgetter = deprecated(
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
