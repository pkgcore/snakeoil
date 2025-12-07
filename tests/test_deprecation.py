import dataclasses
import sys
import warnings

import pytest

from snakeoil.deprecation import Record, Registry, suppress_deprecations

requires_enabled = pytest.mark.skipif(
    not Registry.is_enabled, reason="requires python >=3.13.0"
)


class TestRegistry:
    def test_is_enabled(self):
        assert (sys.version_info >= (3, 13, 0)) == Registry.is_enabled

    @requires_enabled
    def test_it(self):
        r = Registry("tests")
        assert "tests" == r.project
        assert [] == list(r)

        def f(x: int) -> int:
            return x + 1

        f2 = r("test1")(f)
        assert f2 is not f
        assert 1 == len(list(r))
        assert Record(f, "test1", None, None, DeprecationWarning) == list(r)[0]

        with r.suppress_deprecations():
            assert 2 == f2(1)
        if Registry.is_enabled:
            with pytest.deprecated_call():
                assert 2 == f2(1)

        r("test2", removal_in=(5, 3, 0))(f)
        assert 2 == len(list(r))
        assert Record(f, "test2", (5, 3, 0), None, DeprecationWarning) == list(r)[-1]

        r("test3", removal_in_py=(4, 0))(f)
        assert (Record(f, "test3", None, (4, 0), DeprecationWarning)) == list(r)[-1]

        class MyDeprecation(DeprecationWarning): ...

        r("test4", category=MyDeprecation)(f)
        assert (Record(f, "test4", None, None, MyDeprecation)) == list(r)[-1]

    @pytest.mark.skipif(
        Registry.is_enabled, reason="test is only for python 3.12 and lower"
    )
    def test_disabled(self):
        r = Registry("tests")

        def f(): ...

        assert f is r("asdf")(f)
        assert [] == list(r)

    def test_suppress_deprecations(self):
        # assert the convienence function and that we're just reusing the existing.
        assert suppress_deprecations is Registry.suppress_deprecations

        def f(category=DeprecationWarning):
            warnings.warn("deprecation warning was not suppressed", category=category)

        with pytest.warns() as capture:
            with suppress_deprecations():
                f()
            # It's also usable as a decorator
            suppress_deprecations()(f)()
            # pytest.warns requires at least one warning.
            warnings.warn("only allowed warning")
        assert 1 == len(capture.list)
        assert "deprecation warning was not suppressed" not in str(capture.list[0])

    @requires_enabled
    def test_subclassing(self):
        # just assert record class can be extended- so downstream can add more metadata.
        assert Record is Registry("asdf").record_class

        @dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
        class MyRecord(Record):
            extra_val1: int = 1
            extra_val2: int = 2

        def f(): ...

        r = Registry("test", record_class=MyRecord)

        r("asdf", extra_val1=3, extra_val2=4)(f)
        assert 1 == len(list(r))
        assert (
            MyRecord(
                f,
                "asdf",
                None,
                None,
                DeprecationWarning,
                extra_val1=3,
                extra_val2=4,
            )
            == list(r)[0]
        )
