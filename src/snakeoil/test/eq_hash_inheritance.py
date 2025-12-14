__all__ = ("Test",)

from snakeoil._internals import deprecated


@deprecated(
    "This was broken thus disabled long ago.  It's a noop, remove it from your tests",
    removal_in=(0, 12, 0),
)
class Test:
    """Dead set of tests for asserting py2k/py3k compatibility"""
