"""
Deprecation functionally which gracefully degrades if degraded is missing, or <py3.13

All snakeoil code must use this module for deprecation functionality.

Snakeoil *must* work, thus the external dependency on 'degraded' module is desirable but
shouldn't be strictly required- if that module doesn't exist (for whatever reason, despite
deps), warn, and degrade back to >=py3.13 warning.degraded, and if <py3.13, do nothing.

Libraries using snakeoil should decide if they want this or not; pkgcore for example
must use this library for similar 'must work' reasons, but non system critical software
*should* use the degraded module directly for their own code, or use warning.degraded.

That's up to the author.  This exists to allow having the degraded dep but not strictly
require it, while providing shims that look like degraded.degraded if it's not available.
"""

__all__ = ("deprecated",)

import functools
import sys
import warnings
from contextlib import contextmanager

try:
    from deprecated import deprecated as _deprecated_module_func

    @functools.wraps(_deprecated_module_func)
    def deprecated(message, *args, **kwargs):  # pyright: ignore[reportRedeclaration]
        """Shim around deprecated.deprecated enforcing that message is always the first argument"""
        return _deprecated_module_func(*args, **kwargs)
except ImportError:
    warnings.warn(
        "deprecated module could not be imported.  Deprecation messages may not be shown"
    )
    if sys.version_info >= (3, 12, 0):
        # shim it, but drop the deprecated.deprecated metadata.
        def deprecated(message, *args, **kwargs):
            return warnings.deprecated(message)
    else:
        # stupid shitty python 3.11/3.12...
        def deprecated(_message, *args, **kwargs):
            """
            This is disabled in full due to the deprecated module failing to import, and
            inability to fallback since the python version is less than 3.13
            """

            def f(thing):
                return thing

            return f


@contextmanager
def suppress_deprecation_warning():
    # see https://docs.python.org/3/library/warnings.html#temporarily-suppressing-warnings
    with warnings.catch_warnings():
        warnings.simplefilter(action="ignore", category=DeprecationWarning)
        yield
