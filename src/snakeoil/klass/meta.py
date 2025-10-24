__all__ = ("Immutable", "ImmutableStrict")

import functools
from contextlib import contextmanager
from contextvars import ContextVar

_immutable_allow_mutations = ContextVar(
    "immutable_instance_allow_mutation",
    # no object's pointer will ever be zero, so this is safe.
    default=0,
)


class Immutable(type):
    """
    Make instance immutable, but allow __init__ to mutate.

    Like :class:ImmutableStrict, these protections can be sidestepped by
    object.__setatttr__ directly. Additionally for any code decoratored with
    :meth:allow_mutation, mutation is allowed in that invocation.

    Once in a mutation block, anything that block calls is still allowed to
    mutate this instance unless it enters another mutation block (another instance),
    and that block tries to mutate the original instance.  TL;dr: you'll know
    if you hit that edgecase.

    >>> from snakeoil.klass.meta import Immutable
    >>> class foo(metaclass=Immutable):
    ...   def __init__(self):
    ...     self.x = 1 # works
    ...     self._subinit() # works, we're in a mutation context
    ...   def _subinit(self):
    ...     # this only works if invoke in a mutation context.
    ...     # IE, __init__ for example.
    ...     self.x = 2
    >>>
    >>> try: foo().x =1 # doesn't
    ... except AttributeError: pass
    >>>
    >>> try: foo()._subinit() # same thing, this is disallowed
    ... except AttributError: pass

    This is async and thread safe.  It is not safe within generator context
    due to a python limitation.
    """

    default_methods_to_wrap = (
        "__init__",
        "__setstate__",
        # Note, due to the mecahnism relying on id(self), the decorator __del__ can't-
        # even during exception an exception of the mutable block- pin the reference
        # forcing it to stay alive.
        "__del__",
    )

    class Mixin:
        # ensure that if we're in a pure slotted inheritance, we don't break it.
        __slots__ = ()

        @contextmanager
        def __allow_mutation_block__(self):
            """Allow temporary mutation via context manager"""
            last = _immutable_allow_mutations.set(id(self))
            try:
                yield
            finally:
                _immutable_allow_mutations.reset(last)

        def __setattr__(self, name, value):
            if id(self) != _immutable_allow_mutations.get():
                raise AttributeError(self, name, "object is locked against mutation")
            object.__setattr__(self, name, value)

        def __delattr__(self, attr: str):
            if id(self) != _immutable_allow_mutations.get():
                raise AttributeError(self, attr, "object is locked against mutation")
            object.__delattr__(self, attr)

    @functools.wraps(type.__new__)
    def __new__(cls, name, bases, scope) -> type:
        for method in cls.default_methods_to_wrap:
            if f := scope.get(method):
                scope[method] = cls.allow_mutation(f)

        if not any(cls.Mixin in base.mro() for base in bases):
            bases = (cls.Mixin,) + bases

        return super().__new__(cls, name, bases, scope)

    @classmethod
    def allow_mutation(cls, functor):
        """Decorator allowing temporary mutation of an immutable instance"""

        @functools.wraps(functor)
        def f(self, *args, **kwargs):
            with cls.Mixin.__allow_mutation_block__(self):
                return functor(self, *args, **kwargs)

        return f


class ImmutableStrict(type):
    """
    Make instances effectively immutable.

    This is the 'strict' implementation; __setattr__ and __delattr__
    will never allow mutation.  Any mutation- during __init__ for example,
    must be done via object.__setattr__(self, 'attr', value).

    It's strongly advised you look at :class:Simple since that relaxes
    the rules for things like __init__.
    """

    class Mixin:
        __slots__ = ()

        def __setattr__(self, attr, _value):
            raise AttributeError(self, attr)

        def __delattr__(self, attr):
            raise AttributeError(self, attr)

    @functools.wraps(type.__new__)
    def __new__(cls, name, bases, scope):
        if not any(cls.Mixin in base.mro() for base in bases):
            bases = (cls.Mixin,) + bases
        return super().__new__(cls, name, bases, scope)


@functools.lru_cache
def combine_classes(kls: type, *extra: type) -> type:
    """Given a set of classes, combine this as if one had wrote the class by hand

    This is primarily for composing metaclasses on the fly, like thus:

    Effectively:
    class foo(metaclass=combine_metaclasses(kls1, kls2, kls3)): pass

    is the same as if you did this:
    class mkls(kls1, kls2, kls3): pass
    class foo(metaclass=mkls): pass
    """
    klses = [kls]
    klses.extend(extra)

    if len(klses) == 1:
        return kls

    class combined(*klses):
        pass

    combined.__name__ = f"combined_{'_'.join(kls.__qualname__ for kls in klses)}"
    return combined
