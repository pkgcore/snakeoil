__all__ = ("deprecated",)

import warnings
from contextlib import contextmanager

_import_failed = False
try:
    from warnings import deprecated  # pyright: ignore[reportAssignmentType]
except ImportError:
    _import_failed = True

    def deprecated(_message):
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
