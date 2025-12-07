import dataclasses
import sys
import warnings

import pytest

from snakeoil.deprecation import Record, RecordCallable, Registry, suppress_deprecations

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
        assert not r

        def f(x: int) -> int:
            return x + 1

        f2 = r("test1", qualname="asdf")(f)
        assert f2 is not f
        assert 1 == len(list(r))
        assert 1 == len(r)
        assert r
        assert RecordCallable("test1", qualname="asdf") == list(r)[0]

        with r.suppress_deprecations():
            assert 2 == f2(1)
        if Registry.is_enabled:
            with pytest.deprecated_call():
                assert 2 == f2(1)

        r("test2", removal_in=(5, 3, 0), qualname="blah")(f)
        assert 2 == len(r)
        assert (
            RecordCallable("test2", qualname="blah", removal_in=(5, 3, 0))
            == list(r)[-1]
        )

        r("test3", removal_in_py=(4, 0, 0), qualname="test3")(f)
        assert (
            RecordCallable("test3", qualname="test3", removal_in_py=(4, 0, 0))
        ) == list(r)[-1]

        class MyDeprecation(DeprecationWarning): ...

        # just confirm it accepts it.  Post py3.13 add a mock here, should we be truly anal.
        r("test4", category=MyDeprecation, qualname="test4")(f)
        assert (RecordCallable("test4", qualname="test4")) == list(r)[-1]

    @pytest.mark.skipif(
        Registry.is_enabled, reason="test is only for python 3.12 and lower"
    )
    def test_disabled(self):
        r = Registry("tests")

        def f(): ...

        assert f is r("asdf")(f)
        assert not r, f"r should be empty; contents were {r._deprecations}"

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
        assert RecordCallable is Registry("asdf").record_class

        @dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
        class MyRecord(RecordCallable):
            extra_val1: int = 1
            extra_val2: int = 2

        def f(): ...

        r = Registry("test", record_class=MyRecord)

        r("asdf", extra_val1=3, extra_val2=4, qualname="myrecord")(f)
        assert 1 == len(r)
        assert (
            MyRecord(
                "asdf",
                qualname="myrecord",
                extra_val1=3,
                extra_val2=4,
            )
            == list(r)[0]
        )

    def test_expired_deprecations(self):
        r = Registry("asdf")

        def f(): ...

        r("python", removal_in_py=(1, 0, 0))(f)
        r("project", removal_in=(1, 0, 0))(f)
        r(
            "combined",
            removal_in_py=(
                2,
                0,
                0,
            ),
            removal_in=(2, 0, 0),
        )(f)

        assert 3 == len(r)
        assert [] == list(r.expired_deprecations((0, 0, 0), (0, 0, 0)))
        assert ["python"] == [
            x.msg for x in r.expired_deprecations((0, 0, 0), python_version=(1, 0, 0))
        ]
        assert ["project"] == [
            x.msg for x in r.expired_deprecations((1, 0, 0), python_version=(0, 0, 0))
        ]
        assert ["combined", "project", "python"] == list(
            sorted(
                x.msg
                for x in r.expired_deprecations((2, 0, 0), python_version=(2, 0, 0))
            )
        )

    def test_code_directive(self):
        r = Registry("test")
        assert None is r.code_directive(
            "asdf", removal_in=(1, 0, 0), removal_in_py=(2, 0, 0)
        )
        assert 1 == len(r)
        assert (
            Record("asdf", removal_in=(1, 0, 0), removal_in_py=(2, 0, 0)) == list(r)[0]
        )


def test_Record_str():
    assert "removal in version=1.0.2, removal in python=3.0.2, reason: blah" == str(
        Record("blah", removal_in=(1, 0, 2), removal_in_py=(3, 0, 2))
    )


def test_RecordCallable_str():
    assert (
        "qualname='snakeoil.blah.foon', removal in version=2.0.3, reason: I said so"
        == str(
            RecordCallable(
                "I said so", qualname="snakeoil.blah.foon", removal_in=(2, 0, 3)
            )
        )
    )
