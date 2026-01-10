__all__ = ("regexp", "import_module", "is_delayed")

import functools
import importlib
import re
import sys
import types
import typing

from ..obj import BaseDelayedObject, DelayedInstantiation


@functools.wraps(re.compile)
def regexp(pattern: str, flags: int = 0):
    """Lazily compile a regexp; reify it only when it's needed"""
    return DelayedInstantiation(re.Pattern, re.compile, pattern, flags)


def import_module(target: str, force_proxy=False) -> types.ModuleType:
    """Import a module at time of access if it's not already imported.  This is a shim for python's lazy import in 3.15

    :param target: the python namespace path of what to import.  `snakeoil.klass` for example.
    :param force_proxy: Even if the module is in sys.modules, still return a proxy.  This is a break glass
      control only relevant for hard cycle breaking.
    """
    if not force_proxy and (module := sys.modules.get(target, None)) is not None:
        return module
    return DelayedInstantiation(types.ModuleType, importlib.import_module, target)


# Convert this to a type guard when py3.14 is min.
def is_delayed(obj: typing.Any) -> bool:
    cls = object.__getattribute__(obj, "__class__")
    return isinstance(cls, BaseDelayedObject)
