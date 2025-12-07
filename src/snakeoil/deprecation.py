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


import contextlib
import dataclasses
import sys
import typing
import warnings

T = typing.TypeVar("T")
P = typing.ParamSpec("P")

Version: typing.TypeAlias = tuple[int, int, int]
warning_category: typing.TypeAlias = type[Warning]


@dataclasses.dataclass(slots=True, frozen=True)
class Record:
    msg: str
    removal_in: Version | None = None
    removal_in_py: Version | None = None

    def _collect_strings(self) -> typing.Iterator[str]:
        if self.removal_in:
            yield "removal in version=" + (".".join(map(str, self.removal_in)))
        if self.removal_in_py:
            yield "removal in python=" + (".".join(map(str, self.removal_in_py)))
        yield f"reason: {self.msg}"

    def __str__(self) -> str:
        return ", ".join(self._collect_strings())


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class RecordCallable(Record):
    qualname: str

    @classmethod
    def from_callable(cls, thing: typing.Callable, *args, **kwargs) -> "RecordCallable":
        if "locals()" in thing.__qualname__.split("."):
            raise ValueError(
                f"functor {thing!r} has .locals() in it; you need to provide the actual qualname"
            )
        return cls(*args, qualname=thing.__qualname__, **kwargs)

    def _collect_strings(self) -> typing.Iterator[str]:
        yield f"qualname={self.qualname!r}"
        yield from super(RecordCallable, self)._collect_strings()


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

    __slots__ = ("project", "_deprecations", "record_class")

    record_class: type[RecordCallable]

    # Note: snakeoil._internals.deprecated adds the reminder for changing the logic
    # of the Registry once >=3.13.0
    is_enabled: typing.ClassVar[bool] = sys.version_info >= (3, 13, 0)
    _deprecated_callable: typing.Callable | None

    stacklevel: typing.ClassVar[int] = 1 if is_enabled else 0

    if is_enabled:
        from warnings import deprecated as _deprecated_callable

    def __init__(
        self, project: str, /, *, record_class: type[RecordCallable] = RecordCallable
    ):
        self.project = project
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
        removal_in_py: Version | None = None,
        qualname: str | None = None,
        category=DeprecationWarning,
        stacklevel=1,
        **kwargs,
    ):
        """Decorate a callable with a deprecation notice, registering it in the internal list of deprecations

        :param stacklevel: Unlike warnings.deprecated, we account for our own internal stack additions.
           Whatever you pass for this value will be adjusted for our internal frames.  If you need to reach
           one frame up, just pass 1, else 0.
        """

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
                    removal_in_py=removal_in_py,
                    qualname=qualname,
                    **kwargs,
                )
            else:
                r = self.record_class.from_callable(
                    functor,
                    msg,
                    removal_in=removal_in,
                    removal_in_py=removal_in_py,
                    **kwargs,
                )
            self._deprecations.append(r)
            return result

        return f

    def code_directive(
        self,
        msg: str,
        removal_in: Version | None = None,
        removal_in_py: Version | None = None,
    ) -> None:
        if not removal_in and not removal_in_py:
            raise ValueError("either removal_in or removal_in_py must be set")
        """Add a directive in the code that if invoked, records the deprecation"""
        self._deprecations.append(
            Record(msg=msg, removal_in=removal_in, removal_in_py=removal_in_py)
        )

    @staticmethod
    @contextlib.contextmanager
    def suppress_deprecations(
        category: warning_category = DeprecationWarning,
    ):
        """Suppress deprecations within this block.  Usable as a contextmanager or decorator"""
        with warnings.catch_warnings():
            warnings.simplefilter(action="ignore", category=category)
            yield

    # TODO: py3.13, change this to T per the cvar comments
    def __iter__(self) -> typing.Iterator[Record]:
        return iter(self._deprecations)

    def __nonzero__(self) -> bool:
        return bool(self._deprecations)

    def __len__(self) -> int:
        return len(self._deprecations)

    def expired_deprecations(
        self,
        project_version: Version,
        python_version: Version,
    ) -> typing.Iterator[Record]:
        for deprecation in self:
            if (
                deprecation.removal_in is not None
                and project_version >= deprecation.removal_in
            ):
                yield deprecation
            elif (
                deprecation.removal_in_py is not None
                and python_version >= deprecation.removal_in_py
            ):
                yield deprecation


suppress_deprecations = Registry.suppress_deprecations
