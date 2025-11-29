__all__ = ("demand_compile_regexp",)

import re
import sys
import typing

from .delayed import regexp
from .deprecation import deprecated


@deprecated("snakeoil.klass.demand_compile_regexp has moved to snakeoil.delayed.regexp")
def demand_compile_regexp(
    name: str, pattern: str, flags=0, /, scope: dict[str, typing.Any] | None = None
) -> None:
    """Lazily reify a re.compile.

    The mechanism of injecting into the scope is deprecated; move to snakeoil.delayed.regexp.
    """
    if scope is None:
        # Note 2, not 1- we're wrapped in deprecated so we *are* two levels in.
        scope = sys._getframe(2).f_globals
    delayed = regexp(pattern, flags)
    scope[name] = delayed
