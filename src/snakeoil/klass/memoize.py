"""Transparent opportunistic weakref instance caching at instantiation time

Using these classes allows producing singletons from a class definition.  If
an instance of a class is still in memory, created with the same positional
arguments and keyword arguments, that instance *will* be returned.

This should only be used with classes that present an immutable shape.  Anything
mutable should use a registry pattern instead.  By nature of this mechanism you
cannot know if you will get a pre-existing instance from memory or will get a newly
created instance.  These instances are not pinned in memory- they're weakly referenced.
Thus it's strongly advised you use this only with instances that are effectively immutable.

The instance reuse that this allows- a weak reference memoization- allows complex object
creation and whatever expensive actions necessary for that instance, to be effectively
memoized opportunistically.

For the correct architectural patterns, this can *drastically* both reduce memory usage
and reduce runtime.  It's opportunistic reuse of previous work an instance may have done
for things like parsing, or generating chains of other immutable objects- parse byproducts.

Note: this is built on python's weak references.  It will *not* hold an instance in memory.
It cannot optimize reuse where instances are quickly created and destroyed; this should be considered
for scenarios where objects encapsulate things that live for longer period of times.

Whilst python provide class level `__new__`, returned instances from that by the class still
have `__init__` ran- including for pre-existing instances.  This implementation does not
have that problem via leveraging a metaclass.

To use this functionality, either inherit `WeaklyCached` for classes that have no
custom metaclasses in use, or if you use ABC inherit `WeaklyCachedABC`, or if you
have other metaclasses- you can create your own mixup of metaclasses via `WeaklyCachedMeta`.

If the class call has a kwarg of `disable_inst_caching=True`, then that explicitly disable
this functionality for that specific instance.  This should be used when you know that some
component of the args are mutable- or unhashable- at time of the instance creation.

Example usage:

>>> from snakeoil.klass.caching import WeaklyCached
>>> class myfoo(WeaklyCached):
...   counter = 0
...
...   def __init__(self, arg1, arg2, option=None):
...     self.arg1, self.arg2, self.option = arg1, arg2, option
...     self.__class__.counter += 1
>>>
>>> assert myfoo(1, 2, 3) is myfoo(1, 2, 3)
>>> assert myfoo(1, 2, option=3) is myfoo(1, 2, option=3)
>>> assert myfoo(1, 2) is not myfoo(1, 2, 3)
>>> assert myfoo(1, 2) is not myfoo(1, 2, disable_inst_caching=True)

Finally, subclasses *can* disable all caching of this classes instances
via passing `caching=False` in the class definition. `caching=True` is the default.

>>> from snakeoil.klass.caching import WeaklyCached
>>> class foo(WeaklyCached): ...
>>> class foo2(foo, caching=False): ...
>>>
>>> assert foo2() is not foo2()
"""

__all__ = ("WeaklyCached", "WeaklyCachedABC", "WeaklyCachedMeta", "WeaklyCachedABCMeta")

import abc
import inspect
import sys
import types
import typing
import warnings
import weakref

# tuple of positional args, and sorted out keyward args.
T_instance_key = tuple[
    tuple[typing.Hashable, ...], tuple[tuple[str, typing.Hashable], ...]
]


# Why this design requires the metaclass:
#
# A python invocation of `foo(1)` translates to this call stack:
# foo.__class__.__call__(foo, 1) ->
# foo.__new__(foo, 1) -> # return an allocated object to be init'd.
# foo.__init__(self, 1) # only invoked if __new__ returned an isinstance of 'foo'
#
# Python still invokes __init__ even if __new__ returned an already existant (initialized)
# instance; whilst there are dynamic programming tricks involving wrapping __init__ that
# could be implemented, just interceeding in the type.__call__ is *far* more robust
# and simpler.


def raise_at_caller(exc: BaseException, levels: int = 2) -> None:
    """
    rethrow an exception from higher up in the stack.

    Reporting the call line from what flagged the error, when the error is in the caller's
    invocation (and the called just flagged it) is best anchored at the call site.
    """
    frame = sys._getframe(levels)

    tb = types.TracebackType(
        tb_next=None,
        tb_frame=frame,
        tb_lasti=frame.f_lasti,
        tb_lineno=frame.f_lineno,
    )
    raise exc.with_traceback(tb)


def _is_unhashable(obj: typing.Any) -> bool:
    try:
        hash(obj)
    except TypeError:
        return True
    return False


class WeaklyCachedMeta(type):
    """Metaclass implementation used for weakly cached instance reuse

    Use `WeaklyCached` instead for your implementations.  This should only be
    used when you're having to intermix metaclasses.
    """

    __instance_cache__: typing.ClassVar[
        # either a dictionary of hashable args/kwargs to the object, or no instance caching due to class definition.
        weakref.WeakValueDictionary[T_instance_key, "WeaklyCached"] | None
    ]
    __tolerate_uncachable_args__: typing.ClassVar[bool] = False

    def __call__(
        cls,
        *args: typing.Hashable,
        disable_inst_caching=False,
        **kwargs: typing.Hashable,
    ) -> "WeaklyCached":
        if disable_inst_caching or (cache := cls.__instance_cache__) is None:
            return super(WeaklyCachedMeta, cls).__call__(*args, **kwargs)
        key = (args, tuple(sorted(kwargs.items())))

        try:
            if (obj := cache.get(key)) is None:
                obj = cache[key] = super(WeaklyCachedMeta, cls).__call__(
                    *args, **kwargs
                )
        except TypeError as e:
            # Ensure we're about to complain about unhashable, vs the 101 other TypeError's python
            # code can throw.
            if "unhashable" not in str(e):
                raise

            # isolate the offender(s) and rethrow at the line that called us.
            pargs = [(i, x) for i, x in enumerate(args) if _is_unhashable(x)]
            kws = {k: v for k, v in kwargs.items() if _is_unhashable(v)}
            msg = [
                f"It's prohibited to pass unhashable arguments to the WeaklyCached class {cls.__qualname__}"
            ]
            if pargs:
                msg += [
                    f"positional arguments: {', '.join(f'argument {i} value={v!r}' for i, v in pargs)}"
                ]
            if kws:
                msg += [", ".join(f"kwarg {k}={v!r}" for k, v in kws.items())]
            msg = "; ".join(msg)
            if not cls.__tolerate_uncachable_args__:
                raise_at_caller(TypeError(msg))
            warnings.warn(msg, stacklevel=2)
            obj = super(WeaklyCachedMeta, cls).__call__(*args, **kwargs)

        return obj


class WeaklyCachedABCMeta(WeaklyCachedMeta, abc.ABCMeta):
    """Pre-mixed WeaklyCachedMeta with ABC's metaclass

    Use WeaklyCachedABC instead of this metaclass directly.
    """

    __slots__ = ()


class WeaklyCached(metaclass=WeaklyCachedMeta):
    """Reuse existing instances in memory if available.

    This works via hashing the positional and keyword args of an
    instance creation, and using that as a key for looking up
    any previouse instantiation that are still held in memory.

    This explicitly adds a slotted '__weakref__' attribute.  If you inherit
    this class, you do not need to add it yourself.

    Parent class settings are inherited by the child, unless you explicitly override it.
    IE, if you tolerate uncachable arguments in the parent, the children all tolerate it
    unless they state they don't.

    If the parent disables caching, the children have caching disabled unless they re-enable
    it.

    :param caching: if True (the default), all instances of this class will be
        cached.  If ever set to False, children classes have caching disabled until they
        explicitly re-enable it.

    :param tolerate_uncachable_args: if True, calls with unhashable args or kwargs
        will trigger a warning, but will be allowed.  The instance will not be cached
        or reusable.  If False- the default- they will result in a TypeError since the
        instance isn't cachable.

        This inherits the parent's setting, unless explicitly overridden.

        Setting this to True should only be used for transitioning a class to being fully
        cachable.
    """

    __slots__ = ("__weakref__",)

    __child_instance_caching_default__: typing.ClassVar[bool] = True

    def __init_subclass__(
        cls,
        caching: bool | None = None,
        tolerate_uncachable_args: bool | None = None,
        **kwargs,
    ) -> None:
        # integrate this classes directives into the defaults for children, use that to
        # configure ourselves.
        if tolerate_uncachable_args is not None:
            cls.__tolerate_uncachable_args__ = tolerate_uncachable_args

        cls.__child_instance_caching_default__ = (
            cls.__child_instance_caching_default__ if caching is None else caching
        )
        # ABC that are abstract can never be instantiated. No need for a cache.
        if cls.__child_instance_caching_default__ and not inspect.isabstract(cls):
            cls.__instance_cache__ = weakref.WeakValueDictionary()
        else:
            cls.__instance_cache__ = None

        return super(WeaklyCached, cls).__init_subclass__(**kwargs)


class WeaklyCachedABC(WeaklyCached, metaclass=WeaklyCachedABCMeta):
    """Derivative of WeaklyCached that addresses the ABC metaclass conflict.

    If you use ABC for the inheritance chain leading to the class that you wish to weakly cache,
    use this.
    """

    __slots__ = ()
