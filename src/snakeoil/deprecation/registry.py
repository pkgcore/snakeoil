import dataclasses
import sys
import typing
import warnings

from snakeoil import python_namespaces

from .util import suppress_deprecations

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
            for _ in python_namespaces.get_submodules_of(
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
