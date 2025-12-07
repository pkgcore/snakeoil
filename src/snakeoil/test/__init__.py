"""Our unittest extensions."""

__all__ = (
    "coverage",
    "hide_imports",
    "Modules",
    "NamespaceCollector",
    "protect_process",
    "random_str",
    "Slots",
)

import functools
import os
import random
import string
import subprocess
import sys
from unittest.mock import patch

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
        @functools.wraps(functor)
        def _inner_run(self, *args, **kwargs):
            # we're in the child.  Just run it.
            if os.environ.get(marker_env_var, False):
                return functor(self, *args, **kwargs)

            # we're in the parent.  if capsys is in there, we have
            # to intercept it for the code below.
            capsys = kwargs.get("capsys")
            env = os.environ.copy()
            if extra_env:
                env.update(extra_env)
            env[marker_env_var] = "disable"
            test = (
                os.environ["PYTEST_CURRENT_TEST"]
                if forced_test is None
                else forced_test
            )
            # https://docs.pytest.org/en/latest/example/simple.html#pytest-current-test-environment-variable
            assert test.endswith(" (call)")
            test = test[: -len(" (call)")]
            args = [sys.executable, "-m", "pytest", "-v", test]
            p = subprocess.Popen(
                args,
                env=env,
                stdout=None if capsys else subprocess.PIPE,
                stderr=None if capsys else subprocess.PIPE,
            )

            stdout, stderr = p.communicate()
            if capsys:
                result = capsys.readouterr()
                stdout, stderr = result.out, result.err
            ret = p.wait()
            assert ret == 0, (
                f"subprocess run: {args!r}\nnon zero exit: {ret}\nstdout:\n{stdout.decode()}'n\nstderr:\n{stderr.decode()}"
            )

        return _inner_run

    return wrapper


def hide_imports(*import_names: str):
    """Hide imports from the specified modules."""
    orig_import = __import__

    def mock_import(name, *args, **kwargs):
        if name in import_names:
            raise ImportError()
        return orig_import(name, *args, **kwargs)

    return patch("builtins.__import__", side_effect=mock_import)
