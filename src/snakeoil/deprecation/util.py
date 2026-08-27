import functools
import inspect
import typing
import warnings

T = typing.TypeVar("T")
P = typing.ParamSpec("P")


class suppress_deprecations:
    """Suppress deprecations within this block.  Generators and async.Task require special care to function.

    This cannot be used to decorate a generator function.  Using it within a generator requires explicit code flow for it to work correctly whilst not causing suppressions outside of the intended usage.

    The cpython warnings filtering is designed around ContextVar- context specific
    to a thread, an async.Task, etc.  Warnings filtering modifies a context var thus
    suppressions are active only within that context.  Generators do *not* bind to any
    context they started in- whenever they resume, it's resuming in the context of the thing
    that resumed them.

    Do not do this in a generator:
    >>> def f():
    ...   with suppress_deprecations():
    ...     yield invoke_deprecated() # this will be suppressed, but leaks suppression to what consumed us.
    ...
    ...     # in resuming, we have no guarantee we're in the same context as before the yield, where our
    ...     # suppression was added.
    ...     yield invoke_deprecated() # this may or may not be suppressed.

    You have two options.  If you do not need fine grained, wrap the generator; this class will interpose
    between the generator and consumer and prevent this issue.  For example:
    >>> @suppress_deprecations()
    ... def f():
    ...   yield invoke_deprecated()
    ...   yield invoke_deprecated()

    If you need the explicit form, use this:
    >>> def f():
    ...   with suppress_deprecations():
    ...     value = invoke_deprecated() # this will be suppressed
    ...   yield value # we do not force our suppression on the consumer of the generator
    ...   with suppress_deprecations():
    ...     another_value = invoke_deprecated()
    ...   yield another_value

    Decorating a class suppresses deprecations within the methods, classmethods,
    staticmethods and property accessors that the class body defines.  The class
    itself is handed back- it is modified in place- so it stays a class:
    >>> @suppress_deprecations()
    ... class kls:
    ...   def method(self):
    ...     return invoke_deprecated()

    Inherited methods are not touched; they belong to the class that defined
    them.  Neither are nested classes, decorate those directly.
    """

    __slots__ = (
        "_warning_ctx",
        "kwargs",
        "wraps_generators",
    )
    _warnings_ctx: None | warnings.catch_warnings

    def __init__(self, category=DeprecationWarning, wrap_generators=True, **kwargs):
        kwargs.setdefault("action", "ignore")
        kwargs.setdefault("category", category)
        self.kwargs = kwargs
        self.wraps_generators = wrap_generators
        self._warning_ctx = None

    def __enter__(self):
        if self._warning_ctx is not None:
            raise RuntimeError("this contextmanager has already been entered")
        self._warning_ctx = warnings.catch_warnings(**self.kwargs)
        return self._warning_ctx.__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        if (ctx := self._warning_ctx) is None:
            raise RuntimeError("this contextmanager has already exited")
        ret = ctx.__exit__(exc_type, exc_value, traceback)
        self._warning_ctx = None
        return ret

    @typing.overload
    def __call__(self, thing: type[T]) -> type[T]: ...

    @typing.overload
    def __call__(self, thing: typing.Callable[P, T]) -> typing.Callable[P, T]: ...

    def __call__(self, thing):
        # being used as a decorator.
        if isinstance(thing, type):
            return self.__decorate_class(thing)
        return self.__decorate_callable(thing)

    def __decorate_class(self, kls: type[T]) -> type[T]:
        """Suppress deprecations within the callables a class defines"""
        for name, value in list(vars(kls).items()):
            if isinstance(value, (staticmethod, classmethod)):
                value = type(value)(self.__decorate_callable(value.__func__))
            elif isinstance(value, property):
                value = property(
                    *(
                        None if accessor is None else self.__decorate_callable(accessor)
                        for accessor in (value.fget, value.fset, value.fdel)
                    ),
                    value.__doc__,
                )
            elif inspect.isfunction(value):
                value = self.__decorate_callable(value)
            else:
                continue
            setattr(kls, name, value)
        return kls

    def __decorate_callable(
        self, thing: typing.Callable[P, T]
    ) -> typing.Callable[P, T]:
        # We unfortunately need to see the actual call result to know if it's a
        # generator requiring wrapping.
        @functools.wraps(thing)
        def inner(*args: P.args, **kwargs: P.kwargs) -> T:
            # instantiate a new instance.  The callable may result in re-entrancy.
            with (ctx := self.__class__(**self.kwargs)):
                result = thing(*args, **kwargs)
            if inspect.isgenerator(result) and self.wraps_generators:
                return _GeneratorProxy(result, ctx)  # pyright: ignore[reportReturnType]
            return result

        return inner


class _GeneratorProxy:
    """Interposing generator.  Unfortunately this is required due to how coroutines work"""

    __slots__ = (
        "_gen",
        "_ctx",
    )

    def __init__(self, gen: typing.Generator, ctx: suppress_deprecations):
        self._gen = gen
        self._ctx = ctx

    def __iter__(self):
        return self

    def __next__(self):
        with self._ctx:
            return next(self._gen)

    def send(self, val):
        with self._ctx:
            return self._gen.send(val)

    def throw(self, *args):
        return self._gen.throw(*args)

    def close(self):
        with self._ctx:
            self._gen.close()

    def __getattr__(self, attr):
        return getattr(self._gen, attr)
