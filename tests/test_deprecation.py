import dataclasses
import inspect
import sys
import warnings
from textwrap import dedent

import pytest

from snakeoil.deprecation import (
    Record,
    RecordCallable,
    RecordModule,
    RecordNote,
    Registry,
    suppress_deprecations,
)
from snakeoil.python_namespaces import protect_imports

requires_enabled = pytest.mark.skipif(
    not Registry.is_enabled, reason="requires python >=3.13.0"
)


class TestRegistry:
    default_versions = dict(version=(10, 0, 0), python_mininum_version=(10, 0, 0))

    def test_is_enabled(self):
        assert (sys.version_info >= (3, 13, 0)) == Registry.is_enabled

    @requires_enabled
    def test_it(self):
        r = Registry("tests", **self.default_versions)
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

        r("test3", removal_in_python=(4, 0, 0), qualname="test3")(f)
        assert (
            RecordCallable("test3", qualname="test3", removal_in_python=(4, 0, 0))
        ) == list(r)[-1]

        class MyDeprecation(DeprecationWarning): ...

        # just confirm it accepts it.  Post py3.13 add a mock here, should we be truly anal.
        r("test4", category=MyDeprecation, qualname="test4")(f)
        assert (RecordCallable("test4", qualname="test4")) == list(r)[-1]

    @pytest.mark.skipif(
        Registry.is_enabled, reason="test is only for python 3.12 and lower"
    )
    def test_disabled(self):
        r = Registry("tests", **self.default_versions)

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
        assert RecordCallable is Registry("asdf", **self.default_versions).record_class

        @dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
        class MyRecord(RecordCallable):
            extra_val1: int = 1
            extra_val2: int = 2

        def f(): ...

        r = Registry("test", record_class=MyRecord, **self.default_versions)

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

    @requires_enabled
    def test_expired_deprecations(self):
        r = Registry("asdf", **self.default_versions)

        def f(): ...

        r("python", removal_in_python=(1, 0, 0))(f)
        r("project", removal_in=(1, 0, 0))(f)
        r(
            "combined",
            removal_in_python=(
                2,
                0,
                0,
            ),
            removal_in=(2, 0, 0),
        )(f)

        assert 3 == len(r)
        assert [] == list(
            r.expired_deprecations(
                python_version=(0, 0, 0), project_version=(0, 0, 0), force_load=False
            )
        )
        assert ["python"] == [
            x.msg
            for x in r.expired_deprecations(
                project_version=(0, 0, 0), python_version=(1, 0, 0), force_load=False
            )
        ]
        assert ["project"] == [
            x.msg
            for x in r.expired_deprecations(
                project_version=(1, 0, 0), python_version=(0, 0, 0), force_load=False
            )
        ]
        assert ["combined", "project", "python"] == list(
            sorted(
                x.msg
                for x in r.expired_deprecations(
                    project_version=(2, 0, 0),
                    python_version=(2, 0, 0),
                    force_load=False,
                )
            )
        )

    # this is the seul registry functionality which still will test validly in <py3.13.  We flex
    # it solely to confirm we're not causing runtime issues in those environments.
    def test_code_directive(self):
        r = Registry("test", **self.default_versions)
        assert None is r.code_directive(
            "asdf", removal_in=(1, 0, 0), removal_in_python=(2, 0, 0)
        )
        assert 1 == len(r)
        assert (
            RecordNote("asdf", removal_in=(1, 0, 0), removal_in_python=(2, 0, 0))
            == list(r)[0]
        )

    @requires_enabled
    def test_module(self, tmpdir):
        with (tmpdir / "deprecated_import.py").open("w") as f:
            f.write("import this_is_deprecated")
        with (tmpdir / "this_is_deprecated.py").open("w") as f:
            f.write(
                dedent(
                    """
            from snakeoil.deprecation import Registry
            Registry("test", version=(0,0,0), python_mininum_version=(1,0,0)).module('deprecation test', 'this_is_deprecated', removal_in_python=(1,0,0))
            """
                )
            )

        with protect_imports() as (paths, _):
            paths.append(str(tmpdir))
            with pytest.warns() as captures:
                import deprecated_import  # pyright: ignore[reportMissingImports]

        assert 1 == len(captures)
        w = captures[0]
        assert "deprecation test" in str(w)
        assert w.filename.endswith("/deprecated_import.py")
        assert 1 == w.lineno

    def test_suppress_warnings_generators(self):
        # See the docstring of suppress_warnings.  This asserts that the python
        # implementation's generator state mutates the local context, rather than
        # carrying it's only 'subcontext'.  IE, what it does will bleed out the
        # warning suppression.

        # assert no warning filters are going to screw up this test requirements
        with pytest.warns():
            warnings.warn("must be caught", DeprecationWarning)

        # warnings.catch_warnings() cannot be used for these tests since they reset the filters to
        # what the state of it's __enter__.  Meaning any warnings mutations within that block of the generator
        # get undone if you do this:
        # >>> with warnings.catch_warnings():
        # ...   next(f) # it added it's suppressions
        # ... blah # the suppressions from f() got undone by the __exit__ of catch_warnings
        warnings_filters = warnings.filters[:]

        def f():
            with suppress_deprecations():
                warnings.warn("will be caught", DeprecationWarning)
                yield
                warnings.warn(
                    "may not be caught depending on context of resumption",
                    category=DeprecationWarning,
                )

        i = f()
        next(i)
        assert warnings_filters != warnings.filters, (
            f"generator context modifications were limited to the generator frame.  Is this pypi?  a python version >3.15?  See test for assumption notes.  Expected {warnings_filters}, got {warnings.filters}"
        )
        # exhaust it to exit the generators suppression block.
        for _ in i:
            ...
        assert warnings.filters == warnings_filters

        # ... cool.  Now we've asserted the python behavior which is *why* we have a generator specific
        # protection built into it.  Now to validate that works.

        # simple case.  Just yields, not a coroutine
        @suppress_deprecations()
        def iterable():
            warnings.warn("suppressed #1", DeprecationWarning)
            yield 1
            warnings.warn("not suppressed", UserWarning)
            warnings.warn("suppressed #2", DeprecationWarning)
            yield 2
            warnings.warn("suppress #3", DeprecationWarning)

        with warnings.catch_warnings(record=True) as w:
            i = iterable()
            assert 1 == next(i)

            assert 0 == len(w)
            with pytest.warns(UserWarning):
                assert 2 == next(i)
            assert 0 == len(w)
            with pytest.raises(StopIteration):
                next(i)
        assert 0 == len(w)

        # test coroutines.
        @suppress_deprecations()
        def coro():
            warnings.warn("not suppressed", UserWarning)
            warnings.warn("suppress #2", DeprecationWarning)

            received = yield 1
            assert "a1" == received
            warnings.warn("suppress #3", DeprecationWarning)
            received = yield 2
            assert "a2" == received
            warnings.warn("suppress #3", DeprecationWarning)
            warnings.warn("not suppressed", UserWarning)

        with warnings.catch_warnings(record=True) as w:
            gen = coro()
            assert 0 == len(w)  # shouldn't be started by that action alone
            assert inspect.GEN_CREATED == inspect.getgeneratorstate(gen)
            with pytest.warns(UserWarning):
                assert 1 == next(gen)  # start it.
            assert 2 == gen.send("a1")
            with pytest.warns(UserWarning):
                with pytest.raises(StopIteration):
                    gen.send("a2")
        assert 0 == len(w)


def test_RecordModule_str():
    assert "foon.blah: why not, removal in python=3.0.2" == str(
        RecordModule("why not", qualname="foon.blah", removal_in_python=(3, 0, 2))
    )


def test_Record_str():
    assert "blah: removal in version=1.0.2, removal in python=3.0.2" == str(
        Record("blah", removal_in=(1, 0, 2), removal_in_python=(3, 0, 2))
    )


def test_RecordCallable_str():
    assert "snakeoil.blah.foon: I said so, removal in version=2.0.3" == str(
        RecordCallable("I said so", qualname="snakeoil.blah.foon", removal_in=(2, 0, 3))
    )
