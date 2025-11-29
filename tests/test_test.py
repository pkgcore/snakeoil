import os

import pytest

from snakeoil import test


class Test_protect_process:
    def test_success(self, capsys):
        @test.protect_process()
        def no_fail(self) -> None:
            pass

        assert None is no_fail(capsys)
        captured = capsys.readouterr()
        assert "" == captured.out, (
            "no stdout should be captured for success: {captured.out}"
        )
        assert "" == captured.err, (
            "no stderr should be captured for success: {captured.err}"
        )

    def test_failure(self, capsys):
        unique_string = "asdfasdfasdfasdfdasdfdasdfasdfasdfasdfasdfasdfasdfsadf"

        @test.protect_process(extra_env={unique_string: unique_string})
        def fail(self, capsys) -> None:
            raise AssertionError(unique_string)

        if os.environ.get(unique_string):
            # we're in the child.
            fail(self, capsys)
            raise Exception("implementation is broke, fail didn't throw an exception")

        with pytest.raises(AssertionError) as failed:
            fail(self, capsys)

        assert unique_string in str(failed.value)
