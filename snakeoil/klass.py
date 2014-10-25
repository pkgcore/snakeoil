# Copyright: 2006-2011 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""
common class implementations, and optimizations

The functionality contained within this module is of primary use for building
classes themselves and cutting down on a significant amount of boilerplate
involved in writing classes.
"""

from __future__ import print_function

__all__ = ("generic_equality", "reflective_hash", "inject_richcmp_methods_from_cmp",
    "static_attrgetter", "instance_attrgetter", "jit_attr", "jit_attr_none",
    "jit_attr_named", "jit_attr_ext_method", "alias_attr", "cached_hash",
    "cached_property", "cached_property_named",
    "steal_docs", "immutable_instance", "inject_immutable_instance",
    "alias_method")

from collections import deque
from operator import attrgetter

from snakeoil import caching, compatibility
from snakeoil.currying import partial, post_curry
from snakeoil.demandload import demandload
demandload(globals(), 'inspect')


def native_GetAttrProxy(target):
    def reflected_getattr(self, attr):
        return getattr(object.__getattribute__(self, target), attr)
    return reflected_getattr


def native_contains(self, key):
    """
    return True if key is in self, False otherwise
    """
    try:
        self[key]
        return True
    except KeyError:
        return False


def native_get(self, key, default=None):
    """
    return ``default`` if ``key`` is not in self, else the value associated with ``key``
    """
    try:
        return self[key]
    except KeyError:
        return default

_sentinel = object()

_attrlist_getter = attrgetter("__attr_comparison__")
def native_generic_attr_eq(inst1, inst2):
    """
    compare inst1 to inst2, returning True if equal, False if not.

    Comparison is down via comparing attributes listed in inst1.__attr_comparison__
    """
    if inst1 is inst2:
        return True
    for attr in _attrlist_getter(inst1):
        if getattr(inst1, attr, _sentinel) != \
            getattr(inst2, attr, _sentinel):
            return False
    return True


def native_generic_attr_ne(inst1, inst2):
    """
    compare inst1 to inst2, returning True if different, False if equal.

    Comparison is down via comparing attributes listed in inst1.__attr_comparison__
    """
    if inst1 is inst2:
        return False
    for attr in _attrlist_getter(inst1):
        if getattr(inst1, attr, _sentinel) != getattr(inst2, attr, _sentinel):
            return True
    return False


def native_reflective_hash(attr):
    """
    default __hash__ implementation that returns a pregenerated hash attribute

    :param attr: attribute name to pull the hash from on the instance
    :return: hash value for instance this func is used in.
    """
    def __hash__(self):
        return getattr(self, attr)
    return __hash__


class _native_internal_jit_attr(object):

    """
    object implementing the descriptor protocol for use in Just In Time access to attributes.

    Consumers should likely be using the :py:func:`jit_func` line of helper functions
    instead of directly consuming this.
    """

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
            obj = getattr(instance, self.storage_attr, self.singleton)
            if obj is self.singleton:
                obj = self.function(instance)
                self._setter(instance, self.storage_attr, obj)
        return obj


try:
    from snakeoil._klass import (
        GetAttrProxy, contains, get,
        generic_eq as generic_attr_eq, generic_ne as generic_attr_ne,
        reflective_hash, _internal_jit_attr)
except ImportError:
    GetAttrProxy = native_GetAttrProxy
    contains = native_contains
    get = native_get
    generic_attr_eq = native_generic_attr_eq
    generic_attr_ne = native_generic_attr_ne
    reflective_hash = native_reflective_hash
    _internal_jit_attr = _native_internal_jit_attr


def generic_equality(name, bases, scope, real_type=type,
                     eq=generic_attr_eq, ne=generic_attr_ne):
    """
    metaclass generating __eq__/__ne__ methods from an attribute list

    The consuming class must set a class attribute named __attr_comparison__
    that is a sequence- this lists the attributes to compare in determining
    equality.

    :raise: TypeError if __attr_comparison__ is incorrectly defined

    >>> from snakeoil.klass import generic_equality
    >>> class foo(object):
    ...   __metaclass__ = generic_equality
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


def inject_richcmp_methods_from_cmp(scope, inject_always=False):
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
    >>> class foo(object):
    ...
    ...   # note that for this example, we inject always since we're
    ...   # explicitly accessing __ge__ methods- under py2k, they wouldn't
    ...   # exist (__cmp__ would be sufficient).
    ...
    ...   # add the generic rich comparsion methods to the local class namespace
    ...   inject_richcmp_methods_from_cmp(locals(), True)
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
    :param inject_always: normally injection is only done if it's py3k; if True,
        it'll always inject the rich comparison methods
    """

    if not (inject_always or compatibility.is_py3k):
        return
    for key, func in (("__lt__", generic_lt), ("__le__", generic_le),
                      ("__eq__", generic_eq), ("__ne__", generic_ne),
                      ("__ge__", generic_ge), ("__gt__", generic_gt)):
        scope.setdefault(key, func)


class chained_getter(object):

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
    >>> class foo(object):
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
    __metaclass__ = partial(generic_equality, real_type=caching.WeakInstMeta)

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
class _singleton_kls(object):

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
                   uncached_val=_uncached_singleton):
    """
    Version of :py:func:`jit_attr` decorator that allows for explicit control over the
    attribute name used to store the cache value.

    See :py:class:`_internal_jit_attr` for documentation of the misc params.
    """
    return post_curry(kls, stored_attr_name, uncached_val, use_cls_setattr)

def jit_attr_ext_method(func_name, stored_attr_name,
                        use_cls_setattr=False, kls=_internal_jit_attr,
                        uncached_val=_uncached_singleton):
    """
    Decorator handing maximal control of attribute JIT'ing to the invoker.

    See :py:class:`internal_jit_attr` for documentation of the misc params.

    Generally speaking, you only need this when you are doing something rather *special*.
    """

    return kls(alias_method(func_name), stored_attr_name,
        uncached_val, use_cls_setattr)


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
    >>> class foo(object):
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
    `snakeoil.currying.partial` instances for example).
    Example Usage:

    >>> from snakeoil.klass import cached_property_named
    >>> class foo(object):
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
    >>> class foo(object):
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
    >>> class foo(object):
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


def alias_method(attr, name=None, doc=None):
    """at runtime, redirect to another method

    This is primarily useful for when compatibility, or a protocol requires
    you to have the same functionality available at multiple spots- for example
    :py:func:`dict.has_key` and :py:func:`dict.__contains__`.

    :param attr: attribute to redirect to
    :param name: ``__name__`` to force for the new method if desired
    :param doc: ``__doc__`` to force for the new method if desired

    >>> from snakeoil.klass import alias_method
    >>> class foon(object):
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
