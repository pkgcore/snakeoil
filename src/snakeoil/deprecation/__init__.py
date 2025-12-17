"""
Deprecation related functionality.

This provides both a compatibility shim over python versions lacking
warnings.deprecated, while also allowing some very basic extra metadata
to be attached to the deprecation, and tracking all deprecations created
by that registry.  This allows tests to do introspection for deprecations
that can now be removed.

To use this, instantiate a registry, and then use it to decorate functions
(exactly like warnings.deprecated in py3.13).  This just keeps a record of
them so that code analysis can be done for things that need to be removed
when future conditions are met.

"""

__all__ = ("Registry", "RecordCallable", "suppress_deprecations")


import dataclasses
import functools
import inspect
import sys
import typing
import warnings

from snakeoil.python_namespaces import get_submodules_of

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
    """

    __slots__ = (
        "_warning_ctx",
        "kwargs",
        "wraps_generators",
    )
    _warnings_ctx: None | warnings.catch_warnings

    def __init__(self, category=DeprecationWarning, wrap_generators=True, **kwargs):
        kwargs.setdefault("action", "ignore")
        kwargs.setdefault("category", DeprecationWarning)
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

    def __call__(self, thing: typing.Callable[P, T]) -> typing.Callable[P, T]:
        # being used as a decorator.  We unfortunately need to see the actual call result
        # to know if it's a generator requiring wrapping.
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


Version: typing.TypeAlias = tuple[int, int, int]
warning_category: typing.TypeAlias = type[Warning]


@dataclasses.dataclass(slots=True, frozen=True)
class Record:
    msg: str
    removal_in: Version | None = None
    removal_in_python: Version | None = None

    def _collect_strings(self) -> typing.Iterator[str]:
        yield self.msg
        if self.removal_in:
            yield "removal in version=" + (".".join(map(str, self.removal_in)))
        if self.removal_in_python:
            yield "removal in python=" + (".".join(map(str, self.removal_in_python)))

    def __str__(self) -> str:
        i = self._collect_strings()
        thing = next(i)
        rest = ", ".join(i)
        return f"{thing}: {rest}"


class RecordNote(Record):
    __slots__ = ()


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class RecordCallable(Record):
    qualname: str

    @classmethod
    def from_callable(cls, thing: typing.Callable, *args, **kwargs) -> "RecordCallable":
        if "locals()" in thing.__qualname__.split("."):
            raise ValueError(
                f"functor {thing!r} has .locals() in it; you need to provide the actual qualname"
            )
        return cls(*args, qualname=f"{thing.__module__}.{thing.__qualname__}", **kwargs)

    def _collect_strings(self) -> typing.Iterator[str]:
        yield self.qualname
        yield from super(RecordCallable, self)._collect_strings()


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class RecordModule(Record):
    qualname: str

    def _collect_strings(self) -> typing.Iterator[str]:
        yield self.qualname
        yield from super(RecordModule, self)._collect_strings()


# When py3.13 is the min, add a defaulted generic of Record in this, and
# deprecated the init record_class argument.
class Registry:
    """Deprecated notice creation and tracking of deprecations

    This is a no-op for python<3.13 since it's internally built around warnings.deprecated.
    It can be used for compatibility for this reason, and .is_enabled reflects if it's
    actually able to create deprecations, or if it's just in no-op compatibility mode.

    :cvar project: which project these deprecations are for.  This is used as a way to
      restrict analysis of deprecation metadata for the codebase.
    :cvar frame_depth: warnings issued have to be issued at the frame that trigged the warning.
      If you have a deprecated function that reaches up the stack to manipulate a frames scope, this
      is the depth to subtract, the frames from this issuing a deprecation.
      Any subclasses that override __call__ must adjust this value.
    """

    __slots__ = (
        "project",
        "_deprecations",
        "record_class",
        "_qualname",
        "_qualname_suppressions",
        "version",
        "python_mininum_version",
    )

    record_class: type[RecordCallable]

    # Note: snakeoil._internals.deprecated adds the reminder for changing the logic
    # of the Registry once >=3.13.0
    is_enabled: typing.ClassVar[bool] = sys.version_info >= (3, 13, 0)
    _deprecated_callable: typing.Callable | None

    stacklevel: typing.ClassVar[int] = 1 if is_enabled else 0

    if is_enabled:
        _deprecated_callable = warnings.deprecated

    def __init__(
        self,
        project: str,
        /,
        *,
        version: Version,
        python_mininum_version: Version,
        qualname: str | None = None,
        record_class: type[RecordCallable] = RecordCallable,
        qualname_suppressions: typing.Sequence[str] = (),
    ):
        self.project = project
        self._qualname = qualname if qualname is not None else project
        self._qualname_suppressions = tuple(qualname_suppressions)
        self.version = version
        self.python_mininum_version = python_mininum_version
        # TODO: py3.13, change this to T per the cvar comments
        self.record_class = record_class
        self._deprecations: list[Record | RecordCallable] = []
        super().__init__()

    def __call__(
        self,
        msg: str,
        /,
        *,
        removal_in: Version | None = None,
        removal_in_python: Version | None = None,
        qualname: str | None = None,
        category=DeprecationWarning,
        stacklevel=1,
        **kwargs,
    ):
        """Decorate a callable with a deprecation notice, registering it in the internal list of deprecations"""

        def f(functor):
            if not self.is_enabled:
                return functor

            result = typing.cast(typing.Callable, self._deprecated_callable)(
                msg, category=category, stacklevel=stacklevel
            )(functor)

            # unify the below.  That .from_callable is working dataclasses annoying __init__ restrictions.
            if qualname is not None:
                r = self.record_class(
                    msg,
                    removal_in=removal_in,
                    removal_in_python=removal_in_python,
                    qualname=qualname,
                    **kwargs,
                )
            else:
                r = self.record_class.from_callable(
                    functor,
                    msg,
                    removal_in=removal_in,
                    removal_in_python=removal_in_python,
                    **kwargs,
                )
            self._deprecations.append(r)
            return result

        return f

    def code_directive(
        self,
        msg: str,
        removal_in: Version | None = None,
        removal_in_python: Version | None = None,
    ) -> None:
        if not removal_in and not removal_in_python:
            raise ValueError("either removal_in or removal_in_python must be set")
        """Add a directive in the code that if invoked, records the deprecation"""
        self._deprecations.append(
            RecordNote(
                msg=msg, removal_in=removal_in, removal_in_python=removal_in_python
            )
        )

    def module(
        self,
        msg: str,
        qualname: str,
        removal_in: Version | None = None,
        removal_in_python: Version | None = None,
    ) -> None:
        """Deprecation notice that fires for the first import of this module."""
        if not self.is_enabled:
            return
        self._deprecations.append(
            r := RecordModule(
                msg,
                qualname=qualname,
                removal_in=removal_in,
                removal_in_python=removal_in_python,
            )
        )
        # fire the warning; we're triggering it a frame deep from the actual issue (the module itself), thus adjust the stack level
        # to skip us, the module defining the deprecation, and hit the import directly.
        warnings.warn(
            str(r), category=DeprecationWarning, stacklevel=self.stacklevel + 2
        )

    suppress_deprecations = staticmethod(suppress_deprecations)

    # TODO: py3.13, change this to T per the cvar comments
    def __iter__(self) -> typing.Iterator[Record]:
        return iter(self._deprecations)

    def __nonzero__(self) -> bool:
        return bool(self._deprecations)

    def __len__(self) -> int:
        return len(self._deprecations)

    def expired_deprecations(
        self,
        /,
        force_load=True,
        project_version: Version | None = None,
        python_version: Version | None = None,
        with_notes=True,
    ) -> typing.Iterator[Record]:
        """Enumerate the deprecations that exceed the minimum versions

        By default it uses the registries configured norms, but for evaluation of things
        to resolve for upcoming releases, you can override the versioning used.
        """
        project_version = self.version if project_version is None else project_version
        python_version = (
            self.python_mininum_version if python_version is None else python_version
        )
        if force_load:
            for _ in get_submodules_of(
                self._qualname, dont_import=self._qualname_suppressions
            ):
                pass
        for deprecation in self:
            if not with_notes and isinstance(deprecation, RecordNote):
                continue
            if (
                deprecation.removal_in is not None
                and project_version >= deprecation.removal_in
            ):
                yield deprecation
            elif (
                deprecation.removal_in_python is not None
                and python_version >= deprecation.removal_in_python
            ):
                yield deprecation
