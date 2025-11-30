__all__ = ("deprecated",)

import functools
import typing
import warnings
from contextlib import contextmanager

T = typing.TypeVar("T")
P = typing.ParamSpec("P")

_import_failed = False
deprecation_frame_depth = 1  # some old code does "reach up the stack" tricks.  Thus it has to know how far up to climb.
try:
    from warnings import deprecated  # pyright: ignore[reportAttributeAccessIssue]

    deprecation_frame_depth = 2
except ImportError:
    _import_failed = True
    import typing

    def deprecated(_message: str):
        """
        This is a noop; deprecation warnings are disabled for pre python
        3.13.
        """

        def f(thing):
            return thing

        return f


@contextmanager
def suppress_deprecation_warning():
    """
    Used for suppressing all deprecation warnings beneath this

    Use this for known deprecated code that is already addressed, but
    just waiting to die.  Deprecated code calling deprecated code, specifically.
    """
    if _import_failed:
        # noop.
        yield
    else:
        # see https://docs.python.org/3/library/warnings.html#temporarily-suppressing-warnings
        with warnings.catch_warnings():
            warnings.simplefilter(action="ignore", category=DeprecationWarning)
            yield


def suppress_deprecations(thing: typing.Callable[P, T]) -> typing.Callable[P, T]:
    """Decorator to suppress all deprecation warnings within the callable"""

    @functools.wraps(thing)
    def f(*args, **kwargs) -> T:
        with suppress_deprecation_warning():
            return thing(*args, **kwargs)

    return f
