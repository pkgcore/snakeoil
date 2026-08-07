__all__ = ("Simple", "Strict")

import functools
from contextlib import contextmanager
from contextvars import ContextVar
from copyreg import _slotnames  # pyright: ignore[reportAttributeAccessIssue]

_immutable_allow_mutations = ContextVar(
    "immutable_instance_allow_mutation",
    # no object's pointer will ever be zero, so this is safe.
    default=0,
)


def _is_state_pair(state) -> bool:
    """Is this the (__dict__, slots) two tuple `object.__getstate__` produces?"""
    return (
        isinstance(state, tuple)
        and len(state) == 2
        and (state[0] is None or isinstance(state[0], dict))
        and isinstance(state[1], dict)
    )


def _restore_state(self, state):
    """Restore marshalled state, sidestepping the mutation protections.

    Marshalling is a lower level than runtime manipulation of objects, thus this
    doesn't go through __setattr__.  Every shape `object.__getstate__` produces is
    handled: None, a bare __dict__, or the (__dict__, slots) two tuple.

    Note: a subclass overriding __getstate__ to return anything else must supply
    it's own __setstate__.
    """
    if state is None:
        return
    if isinstance(state, dict):
        # a __dict__ only class, or a flat slot mapping from an older snakeoil.
        slots = state
    elif _is_state_pair(state):
        state, slots = state
        if state:
            self.__dict__.update(state)
    else:
        raise TypeError(
            f"{self.__class__.__qualname__} has a custom __getstate__ returning "
            f"{state!r}; it must supply a matching __setstate__"
        )
    if slots:
        setter = object.__setattr__
        for k, v in slots.items():
            setter(self, k, v)


_restore_state.__disable_mutation_autowrapping__ = True  # pyright: ignore[reportFunctionMemberAccess]


def _inject_state_restoration(cls) -> None:
    """Take over state restoration, but only for classes that need it.

    Python restores __dict__ state directly, but slotted state via setattr- which
    these classes block.  Only intercede for the latter; a __setstate__ costs a
    python frame per instance that classes w/out slotting shouldn't pay.
    """
    if _slotnames(cls) and getattr(cls, "__setstate__", None) is None:
        cls.__setstate__ = _restore_state


class Simple:
    """
    Make instance immutable, but allow __init__ to mutate.

    Like :class:Strict, these protections can be sidestepped by
    object.__setatttr__ directly. Additionally for any code decoratored with
    :meth:allow_mutation, mutation is allowed in that invocation.

    Once in a mutation block, anything that block calls is still allowed to
    mutate this instance unless it enters another mutation block (another instance),
    and that block tries to mutate the original instance.  TL;dr: you'll know
    if you hit that edgecase.

    >>> from snakeoil.klass.immutable import Simple
    >>> class foo(Simple):
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

    __slots__ = ()
    __immutable_methods_to_autowrap__ = (
        "__init__",
        "__setstate__",
        # Note, due to the mechanism relying on id(self), the decorator __del__ can't-
        # even during exception an exception of the mutable block- pin the reference
        # forcing it to stay alive.
        "__del__",
    )

    @contextmanager
    def __allow_mutation__(self):
        """Allow temporary mutation via context manager"""
        last = _immutable_allow_mutations.set(id(self))
        try:
            yield
        finally:
            _immutable_allow_mutations.reset(last)

    @classmethod
    def __allow_mutation_wrapper__(cls, functor):
        @functools.wraps(functor)
        def f(instance, *args, **kwargs):
            with cls.__allow_mutation__(instance):
                return functor(instance, *args, **kwargs)

        f.__disable_mutation_autowrapping__ = True  # pyright: ignore[reportAttributeAccessIssue] # it's already wrapped.
        return f

    def __init_subclass__(cls, **kwargs) -> None:
        """Modify the subclass allowing mutation for default allowed methods"""
        for name in cls.__immutable_methods_to_autowrap__:
            if (method := getattr(cls, name, None)) is not None:
                # is it wrapped already or was marked to disable wrapping?
                if not getattr(method, "__disable_mutation_autowrapping__", False):
                    setattr(cls, name, cls.__allow_mutation_wrapper__(method))
        _inject_state_restoration(cls)
        return super().__init_subclass__(**kwargs)

    def __setattr__(self, name, value):
        if id(self) != _immutable_allow_mutations.get():
            raise AttributeError(self, name, "object is locked against mutation")
        object.__setattr__(self, name, value)

    def __delattr__(self, attr: str):
        if id(self) != _immutable_allow_mutations.get():
            raise AttributeError(self, attr, "object is locked against mutation")
        object.__delattr__(self, attr)


class Strict:
    """
    Make instances effectively immutable.

    This is the 'strict' implementation; __setattr__ and __delattr__
    will never allow mutation.  Any mutation- during __init__ for example,
    must be done via object.__setattr__(self, 'attr', value).

    It's strongly advised you look at :class:Simple since that relaxes
    the rules for things like __init__.
    """

    __slots__ = ()

    def __init_subclass__(cls, **kwargs) -> None:
        _inject_state_restoration(cls)
        return super().__init_subclass__(**kwargs)

    def __setattr__(self, attr, _value):
        raise AttributeError(self, attr)

    def __delattr__(self, attr):
        raise AttributeError(self, attr)
