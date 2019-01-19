"""Command-line related exceptions"""


class CliException(Exception):
    """Generic exception with a sane string for non-debug cli output."""


class ExitException(Exception):
    """Generic exception for exiting with a specific return message or status.

    Used in cases where we might want to catch the exception and show a
    traceback for debugging. Note that this is used in place of SystemExit so
    we can differentiate between third party code using SystemExit and our own
    exit method to aid in debugging when necessary.
    """

    def __init__(self, code=None):
        self.code = code
