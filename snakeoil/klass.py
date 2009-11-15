# Copyright: 2006 Brian Harring <ferringb@gmail.com>
# License: GPL2

from operator import attrgetter
from snakeoil.caching import WeakInstMeta
from snakeoil.compatibility import is_py3k
from snakeoil.currying import partial, alias_class_method
from collections import deque

def native_GetAttrProxy(target):
    def reflected_getattr(self, attr):
        return getattr(getattr(self, target), attr)
    return reflected_getattr

def native_contains(self, key):
    try:
        self[key]
        return True
    except KeyError:
        return False

def native_get(self, key, default=None):
    try:
        return self[key]
    except KeyError:
        return default


attrlist_getter = attrgetter("__attr_comparison__")
def native_generic_attr_eq(inst1, inst2, sentinel=object()):
    if inst1 is inst2:
        return True
    for attr in attrlist_getter(inst1):
        if getattr(inst1, attr, sentinel) != \
            getattr(inst2, attr, sentinel):
            return False
    return True

def native_generic_attr_ne(inst1, inst2, sentinel=object()):
    if inst1 is inst2:
        return False
    for attr in attrlist_getter(inst1):
        if getattr(inst1, attr, sentinel) != \
            getattr(inst2, attr, sentinel):
            return True
    return False

try:
    from snakeoil._klass import (GetAttrProxy, contains, get,
        generic_eq as generic_attr_eq, generic_ne as generic_attr_ne)
except ImportError:
    GetAttrProxy = native_GetAttrProxy
    contains = native_contains
    get = native_get
    generic_attr_eq = native_generic_attr_eq
    generic_attr_ne = native_generic_attr_ne


def generic_equality(name, bases, scope, real_type=type,
    eq=generic_attr_eq, ne=generic_attr_ne):
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
    return self.__cmp__(other) < 0

def generic_le(self, other):
    return self.__cmp__(other) <= 0

def generic_eq(self, other):
    return self.__cmp__(other) == 0

def generic_ne(self, other):
    return self.__cmp__(other) != 0

def generic_ge(self, other):
    return self.__cmp__(other) >= 0

def generic_gt(self, other):
    return self.__cmp__(other) > 0

def inject_richcmp_methods_from_cmp(scope, inject_always=False):
    if not (inject_always or is_py3k):
        return
    for key, func in (("__lt__", generic_lt), ("__le__", generic_le),
        ("__eq__", generic_eq), ("__ne__", generic_ne),
        ("__ge__", generic_ge), ("__gt__", generic_gt)):
        scope.setdefault(key, func)


class chained_getter(object):
    __slots__ = ('namespace', 'chain')
    __fifo_cache__ = deque()
    __inst_caching__ = True
    __attr_comparison__ = ("namespace",)
    __metaclass__ = partial(generic_equality, real_type=WeakInstMeta)

    def __init__(self, namespace):
        self.namespace = namespace
        self.chain = tuple(attrgetter(x) for x in namespace.split("."))
        if len(self.__fifo_cache__) > 10:
            self.__fifo_cache__.popleft()
        self.__fifo_cache__.append(self)

    def __hash__(self):
        # XXX shouldn't this hash to self.__class__ in addition?
        # via the __eq__, it won't invalidly be the same, but stil..
        return hash(self.namespace)

    def __call__(self, obj):
        o = obj
        for f in self.chain:
            o = f(o)
        return o


_uncached_singleton = object()

class _internal_jit_attr(object):


    __slots__ = ("_attr_name", "_func", "_setter", "_singleton")

    def __init__(self, func, attr_name, method_lookup=False,
        use_cls_setattr=False, singleton=_uncached_singleton):
        if method_lookup:
            func = alias_class_method(func)
        if use_cls_setattr:
            self._setter = setattr
        else:
            self._setter = object.__setattr__
        self._func = func
        self._attr_name = attr_name
        self._singleton = singleton

    def __get__(self, instance, obj_type):
        obj = getattr(instance, self._attr_name, self._singleton)
        if obj is self._singleton:
            obj = self._func(instance)
            self._setter(instance, self._attr_name, obj)
        return obj

def jit_attr(func, kls=_internal_jit_attr, uncached_val=_uncached_singleton):
    attr_name = "_%s" % func.__name__
    return kls(func, attr_name, singleton=uncached_val)

def jit_attr_none(func, kls=_internal_jit_attr):
    return jit_attr(func, kls=kls, uncached_val=None)

def jit_attr_named(stored_attr_name, use_cls_setattr=False, kls=_internal_jit_attr,
    uncached_val=_uncached_singleton):
    return partial(kls, attr_name=stored_attr_name,
        use_cls_setattr=use_cls_setattr)

def jit_attr_ext_method(func_name, stored_attr_name,
    use_cls_setattr=False, kls=_internal_jit_attr,
    uncached_val=_uncached_singleton):

    return kls(func_name, stored_attr_name, method_lookup=True,
        use_cls_setattr=use_cls_setattr,
        singleton=uncached_val)

def alias_attr(target_attr):
    return property(chained_getter(target_attr))

def cached_hash(func):
    def __hash__(self):
        val = getattr(self, '_hash', None)
        if val is None:
            val = func(self)
            object.__setattr__(self, '_hash', val)
        return val
    return __hash__
