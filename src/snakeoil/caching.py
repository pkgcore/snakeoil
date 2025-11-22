"""
Transparent opportunistic weakref instance caching

:py:class:`WeakInstMeta` is a metaclass designed such that you just add it into
the target class, and instance caching will be done based on the args/keywords
passed to __init__.  Essentially, embedding an opportunistic instance caching
factory into the target class.

There are some caveats to be aware of in using this metaclass:

* If you're doing instance sharing, it's strongly advised you do this only for
  immutable instances.  Generally speaking, you don't want two different codepaths
  modifying the same object (a ORM implementation is a notable exemption to this).
* The implementation doesn't guarantee that it'll always reuse an instance- if the
  args/keywords aren't hashable, this machinery cannot cache the instance.  If the
  invocation of the class differs in positional vs optional arg invocation, it's
  possible to get back a new instance.
* In short, if you're generating a lot of immutable instances and want to
  automatically share instances to lower your memory footprint, WeakInstMeta is
  a good metaclass to use.
* This is weakref caching of instances- it will not force an instance to stay in
  memory, it will only reuse instances that are already in memory.


Simple usage example:

>>> from snakeoil.caching import WeakInstMeta
>>> class myfoo(metaclass=WeakInstMeta):
...   __inst_caching__ = True # safety measure turning caching on
...   counter = 0
...
...   def __init__(self, arg1, arg2, option=None):
...     self.arg1, self.arg2, self.option = arg1, arg2, option
...     self.__class__.counter += 1
>>>
>>> assert myfoo(1, 2, 3) is myfoo(1, 2, 3)
>>> assert myfoo(1, 2, option=3) is myfoo(1, 2, option=3)
>>> assert myfoo(1, 2) is not myfoo(1, 2, 3)
>>> # per caveats, please note that because this invocation differs
>>> # in positional/keywords, instance sharing does not occur-
>>> # despite the fact they're effectively the same to __init__
>>> assert myfoo(2, 3, 4) is not myfoo(1, 2, option=4)
>>>
>>> # finally note that it is weakref'ing the instances.
>>> # we use the counter attribute here since the python allocator
>>> # will sometimes reuse the address if there are no allocations
>>> # between the deletion and creation
>>> o = myfoo(1, 2)
>>> my_count = o.counter
>>> del o
>>> assert my_count != myfoo(1, 2).counter # a new instance is created

"""

__all__ = ("WeakInstMeta",)

import functools
import typing
import warnings
from weakref import WeakValueDictionary


class WeakInstMeta(type):
    """Metaclass for instance caching, resulting in reuse of unique instances.

    few notes-
      - instances must be immutable (or effectively so).
        Since creating a new instance may return a preexisting instance,
        this requirement B{must} be honored.
      - due to the potential for mishap, each subclass of a caching class must
        assign __inst_caching__ = True to enable caching for the derivative.
      - conversely, __inst_caching__ = False does nothing
        (although it's useful as a sign of
        I{do not enable caching for this class}
      - instance caching can be disabled per instantiation via passing
        disabling_inst_caching=True into the class constructor.

    Being a metaclass, the voodoo used doesn't require modification of
    the class itself.

    Examples of usage is the restrictions subsystem for
    U{pkgcore project<http://pkgcore.org>}
    """

    def __new__(cls, name: str, bases: tuple[type, ...], scope, **kwds) -> type:
        if scope.setdefault("__inst_caching__", False):
            scope["__inst_dict__"] = WeakValueDictionary()
            if new_init := scope.get("__init__"):
                # derive a new metaclass on the fly so we can ensure the __call__
                # signature carries the docs/annotations of the __init__ for this class.
                # Basically, show the __init__ doc/annotations, rather than just the bare
                # doc/annotations of cls.__call__
                class c(cls):
                    __call__ = functools.wraps(new_init)(cls.__call__)
                    # wraps passes the original annotations; don't mutate the underlying __init__
                    __call__.__annotations__ = new_init.__annotations__.copy()
                    __call__.__annotations__["disable_inst_caching"] = bool

                c.__name__ = f"_{cls.__name__}_{name}"
                cls = c

        # slotted, unless __weakref__ is explicit, must be added or there must
        # be a parent that isn't slotted (which automatically adds __weakref__)
        if "__slots__" in scope and not any(
            hasattr(base, "__weakref__") for base in bases
        ):
            scope["__slots__"] = tuple(scope["__slots__"]) + ("__weakref__",)

        new_cls = super().__new__(cls, name, bases, scope, **kwds)
        new_cls.__annotations__["__inst_dict__"] = dict[typing.Hashable, typing.Any]
        return new_cls

    def __call__(cls, *a: typing.Hashable, **kw: typing.Hashable):
        """disable caching via disable_inst_caching=True"""
        # This is subtle, but note that this explictly passes "disable_inst_caching" down to the class
        # if the class itself has disabled caching.  This is a debatable design- it means any
        # consumer that disables caching across a semver will throw an exception here.  However,
        # this is historical behavior, thus left this way.
        if not cls.__inst_caching__ or kw.pop("disable_inst_caching", False):  # type: ignore[attr-defined]
            return super(WeakInstMeta, cls).__call__(*a, **kw)

        try:
            key = (a, tuple(sorted(kw.items())))
            if None is (instance := cls.__inst_dict__.get(key)):  # type: ignore[attr-defined]
                instance = cls.__inst_dict__[key] = super(WeakInstMeta, cls).__call__(
                    *a, **kw
                )  # type: ignore[attr-defined]
            return instance
        except TypeError as t:
            warnings.warn(f"caching keys for {cls}, got {t} for a={a}, kw={kw}")
            return super(WeakInstMeta, cls).__call__(*a, **kw)
