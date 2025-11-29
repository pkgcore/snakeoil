__all__ = ("regexp",)

import functools
import re

from ..obj import DelayedInstantiation


@functools.wraps(re.compile)
def regexp(pattern: str, flags: int = 0):
    """Lazily compile a regexp; reify it only when it's needed"""
    return DelayedInstantiation(re.Pattern, re.compile, pattern, flags)
