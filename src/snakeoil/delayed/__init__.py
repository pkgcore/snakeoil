__all__ = ("regexp",)

import functools
import importlib
import re
import types

from ..obj import DelayedInstantiation


@functools.wraps(re.compile)
def regexp(pattern: str, flags: int = 0):
    """Lazily compile a regexp; reify it only when it's needed"""
    return DelayedInstantiation(re.Pattern, re.compile, pattern, flags)


def import_module(target: str) -> types.ModuleType:
    """Import a module at time of access.  This is a shim for python's lazy import in 3.15"""
    return DelayedInstantiation(types.ModuleType, importlib.import_module, target)
