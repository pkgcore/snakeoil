"""
common class implementations, and optimizations

The functionality contained within this module is of primary use for building
classes themselves and cutting down on a significant amount of boilerplate
involved in writing classes.
"""

__all__ = (
    "generic_equality", "reflective_hash", "inject_richcmp_methods_from_cmp",
    "static_attrgetter", "instance_attrgetter", "jit_attr", "jit_attr_none",
    "jit_attr_named", "jit_attr_ext_method", "alias_attr", "cached_hash",
    "cached_property", "cached_property_named",
    "steal_docs", "immutable_instance", "inject_immutable_instance",
    "alias_method", "aliased", "alias", "patch", "SlotsPicklingMixin",
)

from collections import deque
from functools import partial, wraps
from importlib import import_module
import inspect
import itertools
from operator import attrgetter

from . import caching
from .currying import post_curry

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
        if getattr(inst1, attr, sentinel) != \
            getattr(inst2, attr, sentinel):
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


def _internal_jit_attr(
        func, attr_name, singleton=None,
        use_cls_setattr=False, use_singleton=True, doc=None):
    """Object implementing the descriptor protocol for use in Just In Time access to attributes.

    Consumers should likely be using the :py:func:`jit_func` line of helper functions
    instead of directly consuming this.
    """
    doc = getattr(func, '__doc__', None) if doc is None else doc

    class _internal_jit_attr(_raw_internal_jit_attr):
        __doc__ = doc
        __slots__ = ()
    kls = _internal_jit_attr

    return kls(
        func, attr_name, singleton=singleton, use_cls_setattr=use_cls_setattr,
        use_singleton=use_singleton)


class _raw_internal_jit_attr:
    """See _internal_jit_attr; this is an implementation detail of that"""

    __slots__ = ("storage_attr", "function", "_setter", "singleton", "use_singleton")

    def __init__(self, func, attr_name, singleton=None,
                 use_cls_setattr=False, use_singleton=True):
        """
        :param func: function to invoke upon first request for this content
        :param attr_name: attribute name to store the generated value in
        :param singleton: an object to be used with getattr to discern if the
            attribute needs generation/regeneration; this is controllable so
            that consumers can force regeneration of the hash (if they wrote
            None to the attribute storage and singleton was None, it would regenerate
            for example).
        :param use_cls_setattr: if True, the target instances normal __setattr__ is used.
            if False, object.__setattr__ is used.  If the instance is intended as immutable
            (and this is enforced by a __setattr__), use_cls_setattr=True would be warranted
            to bypass that protection for caching the hash value
        :type use_cls_setattr: boolean
        """
        if bool(use_cls_setattr):
            self._setter = setattr
        else:
            self._setter = object.__setattr__
        self.function = func
        self.storage_attr = attr_name
        self.singleton = singleton
        self.use_singleton = use_singleton

    def __get__(self, instance, obj_type):
        if instance is None:
            # accessed from the class, rather than a running instance.
            # access ourself...
            return self
        if not self.use_singleton:
            obj = self.function(instance)
            self._setter(instance, self.storage_attr, obj)
        else:
            try:
                obj = object.__getattribute__(instance, self.storage_attr)
            except AttributeError:
                obj = self.singleton
            if obj is self.singleton:
                obj = self.function(instance)
                self._setter(instance, self.storage_attr, obj)
        return obj


def generic_equality(name, bases, scope, real_type=type,
                     eq=generic_attr_eq, ne=generic_attr_ne):
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
            raise TypeError("all members of attrlist must be strings- "
                            " got %r %s" % (type(x), repr(x)))

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
    if a method already exists, it will not override it.  This behaviour is primarily
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

    for key, func in (("__lt__", generic_lt), ("__le__", generic_le),
                      ("__eq__", generic_eq), ("__ne__", generic_ne),
                      ("__ge__", generic_ge), ("__gt__", generic_gt)):
        scope.setdefault(key, func)


class chained_getter(metaclass=partial(generic_equality, real_type=caching.WeakInstMeta)):

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
    __slots__ = ('namespace', 'getter')
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
        # via the __eq__, it won't invalidly be the same, but stil..
        return hash(self.namespace)

    def __call__(self, obj):
        return self.getter(obj)


static_attrgetter = attrgetter
instance_attrgetter = chained_getter


# we suppress the repr since if it's unmodified, it'll expose the id;
# this annoyingly means our docs have to be recommited every change,
# even if no real code changed (since the id() continually moves)...
class _singleton_kls:

    def __str__(self):
        return "uncached singleton instance"


_uncached_singleton = _singleton_kls


def jit_attr(func, kls=_internal_jit_attr, uncached_val=_uncached_singleton):
    """
    decorator to JIT generate, and cache the wrapped functions result in
    '_' + func.__name__ on the instance.

    :param func: function to wrap
    :param kls: internal arg, overridden if you need a tweaked version of
        :py:class:`_internal_jit_attr`
    :param uncached_val: the value to treat as missing/force regeneration
        when accessing the instance.  Note this normally defaults to a singleton
        that will not be in use anywhere else.
    :return: functor implementing the described behaviour
    """
    attr_name = "_%s" % func.__name__
    return kls(func, attr_name, uncached_val, False)


def jit_attr_none(func, kls=_internal_jit_attr):
    """
    Version of :py:func:`jit_attr` decorator that forces the uncached_val
    to None.

    This is mainly useful so that if any out of band forced regeneration of
    the value, they know they just have to write None to the attribute to
    force regeneration.
    """
    return jit_attr(func, kls=kls, uncached_val=None)


def jit_attr_named(stored_attr_name, use_cls_setattr=False, kls=_internal_jit_attr,
                   uncached_val=_uncached_singleton, doc=None):
    """
    Version of :py:func:`jit_attr` decorator that allows for explicit control over the
    attribute name used to store the cache value.

    See :py:class:`_internal_jit_attr` for documentation of the misc params.
    """
    return post_curry(kls, stored_attr_name, uncached_val, use_cls_setattr, doc=doc)


def jit_attr_ext_method(func_name, stored_attr_name,
                        use_cls_setattr=False, kls=_internal_jit_attr,
                        uncached_val=_uncached_singleton, doc=None):
    """
    Decorator handing maximal control of attribute JIT'ing to the invoker.

    See :py:class:`internal_jit_attr` for documentation of the misc params.

    Generally speaking, you only need this when you are doing something rather *special*.
    """

    return kls(alias_method(func_name), stored_attr_name,
               uncached_val, use_cls_setattr, doc=doc)


def cached_property(func, kls=_internal_jit_attr, use_cls_setattr=False):
    """
    like `property`, just with caching

    This is usable in classes that aren't using slots; it exploits python
    lookup ordering such that on first access, the function is invoked generating
    the desired attribute.  It then assigns that content to the same name as the
    property- directly into the instance dictionary.  Subsequent accesses will
    find the value in the instance dictionary first- essentially just as fast
    as normal attribute access, just w/ the ability to generate the instance
    on first access (or to wipe the attribute and force a regeneration).

    Example Usage:

    >>> from snakeoil.klass import cached_property
    >>> class foo:
    ...
    ...   @cached_property
    ...   def attr(self):
    ...     print("invoked")
    ...     return 1
    >>>
    >>> obj = foo()
    >>> print(obj.attr)
    invoked
    1
    >>> print(obj.attr)
    1
    """
    return kls(func, func.__name__, None, use_singleton=False,
               use_cls_setattr=use_cls_setattr)


def cached_property_named(name, kls=_internal_jit_attr, use_cls_setattr=False):
    """
    variation of `cached_property`, just with the ability to explicitly set the attribute name

    Primarily of use for when the functor it's wrapping has a generic name (
    `functools.partial` instances for example).
    Example Usage:

    >>> from snakeoil.klass import cached_property_named
    >>> class foo:
    ...
    ...   @cached_property_named("attr")
    ...   def attr(self):
    ...     print("invoked")
    ...     return 1
    >>>
    >>> obj = foo()
    >>> print(obj.attr)
    invoked
    1
    >>> print(obj.attr)
    1
    """
    return post_curry(kls, name, use_singleton=False, use_cls_setattr=False)


def alias_attr(target_attr):
    """
    return a property that will alias access to target_attr

    target_attr can be multiple getattrs in addition- ``x.y.z`` is valid for example

    Example Usage:

    >>> from snakeoil.klass import alias_attr
    >>> class foo:
    ...
    ...   seq = (1,2,3)
    ...
    ...   def __init__(self, a=1):
    ...     self.a = a
    ...
    ...   b = alias_attr("a")
    ...   recursive = alias_attr("seq.__hash__")
    >>>
    >>> o = foo()
    >>> print(o.a)
    1
    >>> print(o.b)
    1
    >>> print(o.recursive == foo.seq.__hash__)
    True
    """
    return property(instance_attrgetter(target_attr),
                    doc="alias to %s" % (target_attr,))


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
        val = getattr(self, '_hash', None)
        if val is None:
            val = func(self)
            object.__setattr__(self, '_hash', val)
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
        components = target.split('.')
        import_path = components.pop(0)
        module = import_module(import_path)
        for comp in components:
            try:
                module = getattr(module, comp)
            except AttributeError:
                import_path += ".%s" % comp
                module = import_module(import_path)
        return module

    def _get_target(target):
        try:
            module, attr = target.rsplit('.', 1)
        except (TypeError, ValueError):
            raise TypeError("invalid target: %r" % (target,))
        module = _import_module(module)
        return module, attr

    def decorator(func):
        # use the original function wrapper
        func = getattr(func, '_func', func)

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


def _immutable_setattr(self, attr, value):
    raise AttributeError(self, attr)


def _immutable_delattr(self, attr):
    raise AttributeError(self, attr)


def immutable_instance(name, bases, scope, real_type=type):
    """metaclass that makes instances of this class effectively immutable

    It still is possible to do object.__setattr__ to get around it during
    initialization, but usage of this class effectively prevents accidental
    modification, instead requiring explicit modification."""
    inject_immutable_instance(scope)
    return real_type(name, bases, scope)


def inject_immutable_instance(scope):
    """inject immutable __setattr__ and __delattr__ implementations

    see immutable_instance for further details

    :param scope: mapping to modify, inserting __setattr__ and __delattr__
      methods if they're not yet defined.
    """
    scope.setdefault("__setattr__", _immutable_setattr)
    scope.setdefault("__delattr__", _immutable_delattr)


class ImmutableInstance:
    """Class that disables surface-level attribute modifications."""

    __setattr__ = _immutable_setattr
    __delattr__ = _immutable_delattr

    def __getstate__(self):
        return self.__dict__.copy()

    def __setstate__(self, state):
        for k, v in state.items():
            object.__setattr__(self, k, v)


def alias_method(attr, name=None, doc=None):
    """at runtime, redirect to another method

    This is primarily useful for when compatibility, or a protocol requires
    you to have the same functionality available at multiple spots- for example
    :py:func:`dict.has_key` and :py:func:`dict.__contains__`.

    :param attr: attribute to redirect to
    :param name: ``__name__`` to force for the new method if desired
    :param doc: ``__doc__`` to force for the new method if desired

    >>> from snakeoil.klass import alias_method
    >>> class foon:
    ...   def orig(self):
    ...     return 1
    ...   alias = alias_method("orig")
    >>> obj = foon()
    >>> assert obj.orig() == obj.alias()
    >>> assert obj.alias() == 1
    """
    grab_attr = static_attrgetter(attr)

    def _asecond_level_call(self, *a, **kw):
        return grab_attr(self)(*a, **kw)

    if doc is None:
        doc = "Method alias to invoke :py:meth:`%s`." % (attr,)

    _asecond_level_call.__doc__ = doc
    if name:
        _asecond_level_call.__name__ = name
    return _asecond_level_call


class alias:
    """Decorator for making methods callable through aliases.

    This decorator must be used inside a class decorated with @aliased.

    Example usage:

    >>> from snakeoil.klass import aliased, alias
    >>> @aliased
    >>> class Speak:
    ...     @alias('yell', 'scream')
    ...     def shout(message):
    ...         return message.upper()
    >>>
    >>> speak = Speak()
    >>> assert speak.shout('foo') == speak.yell('foo') == speak.scream('foo')
    """
    def __init__(self, *aliases):
        self.aliases = set(aliases)

    def __call__(self, func):
        func._aliases = self.aliases
        return func


def aliased(cls):
    """Class decorator used in combination with @alias method decorator."""
    orig_methods = cls.__dict__.copy()
    seen_aliases = set()
    for name, method in orig_methods.items():
        if hasattr(method, '_aliases'):
            collisions = method._aliases.intersection(orig_methods.keys() | seen_aliases)
            if collisions:
                raise ValueError(
                    "aliases collide with existing attributes: %s" % (
                    {', '.join(collisions)},))
            seen_aliases |= method._aliases
            for alias in method._aliases:
                setattr(cls, alias, method)
    return cls


class SlotsPicklingMixin:
    """Default pickling support for classes that use __slots__."""

    __slots__ = ()

    def __getstate__(self):
        all_slots = itertools.chain.from_iterable(
            getattr(t, '__slots__', ()) for t in type(self).__mro__)
        state = {attr: getattr(self, attr) for attr in all_slots
                 if hasattr(self, attr) and attr != '__weakref__'}
        return state

    def __setstate__(self, state):
        for k, v in state.items():
            object.__setattr__(self, k, v)
