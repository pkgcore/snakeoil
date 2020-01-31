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

import warnings
from weakref import WeakValueDictionary


class native_WeakInstMeta(type):
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
    def __new__(cls, name, bases, d):
        if d.get("__inst_caching__", False):
            d["__inst_caching__"] = True
            d["__inst_dict__"] = WeakValueDictionary()
        else:
            d["__inst_caching__"] = False
        slots = d.get('__slots__')
        # get ourselves a singleton to be safe...
        o = object()
        if slots is not None:
            for base in bases:
                if getattr(base, '__weakref__', o) is not o:
                    break
            else:
                d['__slots__'] = tuple(slots) + ('__weakref__',)
        return type.__new__(cls, name, bases, d)

    def __call__(cls, *a, **kw):
        """disable caching via disable_inst_caching=True"""
        if cls.__inst_caching__ and not kw.pop("disable_inst_caching", False):
            kwlist = list(kw.items())
            kwlist.sort()
            key = (a, tuple(kwlist))
            try:
                instance = cls.__inst_dict__.get(key)
            except (NotImplementedError, TypeError) as t:
                warnings.warn(
                    "caching keys for %s, got %s for a=%s, kw=%s" % (
                        cls, t, a, kw))
                del t
                key = instance = None

            if instance is None:
                instance = super(native_WeakInstMeta, cls).__call__(*a, **kw)

                if key is not None:
                    cls.__inst_dict__[key] = instance
        else:
            instance = super(native_WeakInstMeta, cls).__call__(*a, **kw)

        return instance


# "Invalid name"
# pylint: disable=C0103

try:
    # No name in module
    # pylint: disable=E0611
    from ._caching import WeakInstMeta
    cpy_WeakInstMeta = WeakInstMeta
except ImportError:
    cpy_WeakInstMeta = None
    WeakInstMeta = native_WeakInstMeta
