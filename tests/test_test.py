import os

import pytest

from snakeoil import test


class Test_protect_process:
    def test_success(self, pytestconfig, capsys, in_child=False):
        @test.protect_process()
        def no_fail() -> None:
            pass

        if no_fail.__protect_process_is_child__:  # pyright: ignore[reportFunctionMemberAccess]
            assert None is no_fail()
            return

        assert None is no_fail(pytestconfig=pytestconfig)  # pyright: ignore[reportCallIssue]
        if in_child:
            return
        captured = capsys.readouterr()
        assert "" == captured.out, (
            "no stdout should be captured for success: {captured.out}"
        )
        assert "" == captured.err, (
            "no stderr should be captured for success: {captured.err}"
        )

    def test_failure(self, pytestconfig):
        unique_string = "asdfasdfasdfasdfdasdfdasdfasdfasdfasdfasdfasdfasdfsadf"

        @test.protect_process(extra_env={unique_string: unique_string})
        def fail() -> None:
            raise AssertionError(unique_string)

        if fail.__protect_process_is_child__:  # pyright: ignore[reportFunctionMemberAccess]
            is_in_env = os.environ.get(unique_string) == unique_string
            assert is_in_env, (
                "unique_string wasn't in the child.  extra_env didn't pass down"
            )
            # trigger the exception.
            fail()
            # chuck this if we make it this far, because it means fail is misimplemented or
            # protect_process didn't return the raw functor to run
            raise Exception("implementation is broke, fail didn't throw an exception")

        with pytest.raises(AssertionError) as failed:
            fail(pytestconfig=pytestconfig)  # pyright: ignore[reportCallIssue]

        assert unique_string in str(failed.value)
