__all__ = ("demand_compile_regexp",)

import sys
import typing

from snakeoil._internals import deprecated

from .delayed import regexp


@deprecated(
    "Use snakeoil.delayed.regexp which no longer relies on scope trickery",
    removal_in=(0, 12, 0),
)
def demand_compile_regexp(
    name: str, pattern: str, flags=0, /, scope: dict[str, typing.Any] | None = None
) -> None:
    """Lazily reify a re.compile.

    The mechanism of injecting into the scope is deprecated; move to snakeoil.delayed.regexp.
    """
    if scope is None:
        scope = sys._getframe(deprecated.stacklevel + 1).f_globals
    delayed = regexp(pattern, flags)
    scope[name] = delayed
