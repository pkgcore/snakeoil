"""JIT related function"""

__all__ = (
    "jit_attr",
    "jit_attr_none",
    "jit_attr_named",
    "jit_attr_ext_method",
)
# we suppress the repr since if it's unmodified, it'll expose the id;
# this annoyingly means our docs have to be recommitted every change,
# even if no real code changed (since the id() continually moves)...
import operator
import typing

from ..currying import post_curry


class kls:
    __slots__ = ()

    def __str__(self):
        return "uncached singleton instance"


_uncached_singleton = kls()
del kls


def _internal_jit_attr(
    func, attr_name, singleton=None, use_cls_setattr=False, use_singleton=True, doc=None
):
    """Object implementing the descriptor protocol for use in Just In Time access to attributes.

    Consumers should likely be using the :py:func:`jit_func` line of helper functions
    instead of directly consuming this.
    """
    doc = getattr(func, "__doc__", None) if doc is None else doc

    class _internal_jit_attr(_raw_internal_jit_attr):
        __doc__ = doc
        __slots__ = ()

    kls = _internal_jit_attr

    return kls(
        func,
        attr_name,
        singleton=singleton,
        use_cls_setattr=use_cls_setattr,
        use_singleton=use_singleton,
    )


class _raw_internal_jit_attr:
    """See _internal_jit_attr; this is an implementation detail of that"""

    __slots__ = ("storage_attr", "function", "_setter", "singleton", "use_singleton")

    def __init__(
        self, func, attr_name, singleton=None, use_cls_setattr=False, use_singleton=True
    ):
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


T = typing.TypeVar("T")


def jit_attr(
    func: typing.Callable[[typing.Any], T],
    kls=_internal_jit_attr,
    uncached_val: typing.Any = _uncached_singleton,
) -> T:
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
    attr_name = f"_{func.__name__}"
    return kls(func, attr_name, uncached_val, False)


def jit_attr_none(func: typing.Callable[[typing.Any], T], kls=_internal_jit_attr) -> T:
    """
    Version of :py:func:`jit_attr` decorator that forces the uncached_val
    to None.

    This is mainly useful so that if any out of band forced regeneration of
    the value, they know they just have to write None to the attribute to
    force regeneration.
    """
    return jit_attr(func, kls=kls, uncached_val=None)


def jit_attr_named(
    stored_attr_name: str,
    use_cls_setattr=False,
    kls=_internal_jit_attr,
    uncached_val: typing.Any = _uncached_singleton,
    doc=None,
):
    """
    Version of :py:func:`jit_attr` decorator that allows for explicit control over the
    attribute name used to store the cache value.

    See :py:class:`_internal_jit_attr` for documentation of the misc params.
    """
    return post_curry(kls, stored_attr_name, uncached_val, use_cls_setattr, doc=doc)


def jit_attr_ext_method(
    func_name: str,
    stored_attr_name: str,
    use_cls_setattr=False,
    kls=_internal_jit_attr,
    uncached_val: typing.Any = _uncached_singleton,
    doc=None,
):
    """
    Decorator handing maximal control of attribute JIT'ing to the invoker.

    See :py:class:`internal_jit_attr` for documentation of the misc params.

    Generally speaking, you only need this when you are doing something rather *special*.
    """

    return kls(
        alias_method(func_name),
        stored_attr_name,
        uncached_val,
        use_cls_setattr,
        doc=doc,
    )


def cached_property(
    func: typing.Callable[[typing.Any], T],
    kls=_internal_jit_attr,
    use_cls_setattr=False,
) -> T:
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
    return kls(
        func, func.__name__, None, use_singleton=False, use_cls_setattr=use_cls_setattr
    )


def cached_property_named(name: str, kls=_internal_jit_attr, use_cls_setattr=False):
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
    return post_curry(kls, name, use_singleton=False, use_cls_setattr=use_cls_setattr)


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
    return property(operator.attrgetter(target_attr), doc=f"alias to {target_attr}")


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
    grab_attr = operator.attrgetter(attr)

    def _asecond_level_call(self, *a, **kw):
        return grab_attr(self)(*a, **kw)

    if doc is None:
        doc = f"Method alias to invoke :py:meth:`{attr}`."

    _asecond_level_call.__doc__ = doc
    if name:
        _asecond_level_call.__name__ = name
    return _asecond_level_call
