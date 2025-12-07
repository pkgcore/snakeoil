__all__ = ("Test",)

from snakeoil._internals import deprecated


@deprecated(
    "snakeoil.test.eq_hash_inheritance.Test is a noop.  Remove it from your tests",
    removal_in=(0, 12, 0),
)
class Test:
    """Dead set of tests for asserting py2k/py3k compatibility"""
