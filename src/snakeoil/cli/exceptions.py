"""Command-line related exceptions"""

from ..errors import walk_exception_chain


class UserException(Exception):
    """Generic exception with a sane string for non-debug, user-facing output."""

    def __init__(self, msg, verbosity=None):
        super().__init__(msg)
        self._verbosity = verbosity

    def msg(self, verbosity=0):
        return ''


class ExitException(Exception):
    """Generic exception for exiting with a specific return message or status.

    Used in cases where we might want to catch the exception and show a
    traceback for debugging. Note that this is used in place of SystemExit so
    we can differentiate between third party code using SystemExit and our own
    exit method to aid in debugging when necessary.
    """

    def __init__(self, code=None):
        self.code = code


def find_user_exception(exc):
    """Find the UserException related to a given exception if one exists."""
    try:
        return next(e for e in walk_exception_chain(exc) if isinstance(e, UserException))
    except StopIteration:
        return None
