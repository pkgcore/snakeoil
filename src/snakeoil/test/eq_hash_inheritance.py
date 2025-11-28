__all__ = ("Test",)

from ..deprecation import deprecated


@deprecated(
    "snakeoil.test.eq_hash_inheritance.Test is a noop.  Remove it from your tests"
)
class Test:
    """Dead set of tests for asserting py2k/py3k compatibility"""
