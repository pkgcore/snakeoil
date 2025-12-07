"""Our unittest extensions."""

__all__ = (
    "AbstractTest",
    "coverage",
    "hide_imports",
    "Modules",
    "NamespaceCollector",
    "protect_process",
    "random_str",
    "Slots",
)


import os
import random
import string
import subprocess
import sys
from unittest.mock import patch

from .abstract import AbstractTest
from .code_quality import Modules, NamespaceCollector, Slots


def random_str(length):
    """Return a random string of specified length."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def coverage():
    """Extract coverage instance (if it exists) from the current running context."""
    cov = None
    import inspect

    try:
        import coverage

        frame = inspect.currentframe()
        while frame is not None:
            cov = getattr(frame.f_locals.get("self"), "coverage", None)
            if isinstance(cov, coverage.coverage):
                break
            frame = frame.f_back
    except ImportError:
        pass
    return cov


def protect_process(
    forced_test: None | str = None,
    marker_env_var="SNAKEOIL_UNITTEST_PROTECT_PROCESS",
    extra_env: dict[str, str] | None = None,
):
    def wrapper(functor):
        if os.environ.get(marker_env_var, False):
            functor.__protect_process_is_child__ = True
            return functor

        @staticmethod
        def parent_runner(pytestconfig):
            env = os.environ.copy()
            if extra_env:
                env.update(extra_env)
            env[marker_env_var] = "in_child"
            test = (
                os.environ["PYTEST_CURRENT_TEST"]
                if forced_test is None
                else forced_test
            )
            # https://docs.pytest.org/en/latest/example/simple.html#pytest-current-test-environment-variable
            assert test.endswith(" (call)")
            test = test[: -len(" (call)")]
            # pytestconfig.rootpath is used so that if someone has cd'd within the tests directory, the test
            # can still be found.  PYTEST_CURRENT_TEST is rooted against the root, thus this requirement
            args = [
                sys.executable,
                "-m",
                "pytest",
                "-v",
                f"{pytestconfig.rootpath}/{test}",
            ]
            p = subprocess.Popen(
                args,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            stdout, stderr = p.communicate()
            exit_code = p.wait()
            assert 0 == exit_code, (
                f"subprocess run: {args!r}\nnon zero exit: {exit_code}\nstdout:\n{stdout.decode()}'n\nstderr:\n{stderr.decode()}"
            )

        # do not do a functools wraps; it'll stomp our pytestconfig signature.  Just do basic transfer.
        for a in ("__name__", "__module__", "__qualname__"):
            if (val := getattr(functor, a, None)) is not None:
                setattr(parent_runner, a, val)
        parent_runner.__protect_process_is_child__ = False
        return parent_runner

    return wrapper


def hide_imports(*import_names: str):
    """Hide imports from the specified modules."""
    orig_import = __import__

    def mock_import(name, *args, **kwargs):
        if name in import_names:
            raise ImportError()
        return orig_import(name, *args, **kwargs)

    return patch("builtins.__import__", side_effect=mock_import)
