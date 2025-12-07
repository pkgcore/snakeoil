"""
Deprecation related functionality.

This provides both a compatibility shim over python versions lacking
warnings.deprecated, while also allowing some very basic extra metadata
to be attached to the deprecation, and tracking all deprecations created
by that registry.  This allows tests to do introspection for deprecations
that can now be removed.

"""

__all__ = ("Registry", "Record", "suppress_deprecations")


import contextlib
import dataclasses
import sys
import typing
import warnings

T = typing.TypeVar("T")
P = typing.ParamSpec("P")

Version: typing.TypeAlias = tuple[int, ...] | None
warning_category: typing.TypeAlias = type[Warning]


@dataclasses.dataclass(slots=True, frozen=True)
class Record:
    thing: typing.Callable
    msg: str
    removal_in: Version = None
    removal_in_py: Version = None
    category: warning_category = DeprecationWarning


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

    record_class: type[Record]

    is_enabled: typing.ClassVar[bool] = sys.version_info >= (3, 13, 0)
    _deprecated_callable: typing.Callable | None

    # Certain nasty python code that is deprecated lookups up the stack to do
    # scope manipulation; document the number of frames we add if we're interposed
    # between their target scope and their execution.
    stacklevel: typing.ClassVar[int] = 1 if is_enabled else 0

    if is_enabled:
        from warnings import deprecated as _deprecated_callable

    def __init__(self, project: str, /, *, record_class: type[Record] = Record):
        self.project = project
        # TODO: py3.13, change this to T per the cvar comments
        self.record_class = record_class
        self._deprecations: list[Record] = []
        super().__init__()

    def __call__(
        self,
        msg: str,
        /,
        *,
        removal_in: Version = None,
        removal_in_py: Version = None,
        category: warning_category = DeprecationWarning,
        **kwargs,
    ):
        """Decorate a callable with a deprecation notice, registering it in the internal list of deprecations"""

        def f(thing):
            if not self.is_enabled:
                return thing

            result = typing.cast(typing.Callable, self._deprecated_callable)(
                msg,
                category=category,
                stacklevel=kwargs.pop("stacklevel", 1),
            )(thing)

            self._deprecations.append(
                self.record_class(
                    thing,
                    msg,
                    category=category,
                    removal_in=removal_in,
                    removal_in_py=removal_in_py,
                    **kwargs,
                )
            )
            return result

        return f

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


suppress_deprecations = Registry.suppress_deprecations
