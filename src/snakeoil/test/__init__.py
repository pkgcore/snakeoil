"""Our unittest extensions."""

import os
import random
import string
import subprocess
import sys
from unittest.mock import patch

# not relative imports so protect_process() works properly
from snakeoil import klass


def random_str(length):
    """Return a random string of specified length."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def coverage():
    """Extract coverage instance (if it exists) from the current running context."""
    cov = None
    import inspect
    try:
        import coverage
        frame = inspect.currentframe()
        while frame is not None:
            cov = getattr(frame.f_locals.get('self'), 'coverage', None)
            if isinstance(cov, coverage.coverage):
                break
            frame = frame.f_back
    except ImportError:
        pass
    return cov


@klass.patch('os._exit')
def _os_exit(orig_exit, val):
    """Monkeypatch os._exit() to save coverage data before exit."""
    cov = coverage()
    if cov is not None:
        cov.stop()
        cov.save()
    orig_exit(val)


_PROTECT_ENV_VAR = "SNAKEOIL_UNITTEST_PROTECT_PROCESS"


def protect_process(functor, name=None):
    def _inner_run(self, name=name):
        if os.environ.get(_PROTECT_ENV_VAR, False):
            return functor(self)
        if name is None:
            name = f"{self.__class__.__module__}.{self.__class__.__name__}.{method_name}"
        runner_path = __file__
        if runner_path.endswith(".pyc") or runner_path.endswith(".pyo"):
            runner_path = runner_path.rsplit(".", maxsplit=1)[0] + ".py"
        wipe = _PROTECT_ENV_VAR not in os.environ
        try:
            os.environ[_PROTECT_ENV_VAR] = "yes"
            args = [sys.executable, __file__, name]
            p = subprocess.Popen(args, shell=False, env=os.environ.copy(),
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            stdout, _ = p.communicate()
            ret = p.wait()
            assert ret == 0, f"subprocess run: {args!r}\nnon zero exit: {ret}\nstdout:\n{stdout}"
        finally:
            if wipe:
                os.environ.pop(_PROTECT_ENV_VAR, None)

    for x in ("__doc__", "__name__"):
        if hasattr(functor, x):
            setattr(_inner_run, x, getattr(functor, x))
    method_name = getattr(functor, '__name__', None)
    return _inner_run


def hide_imports(*import_names: str):
    """Hide imports from the specified modules."""
    orig_import = __import__

    def mock_import(name, *args, **kwargs):
        if name in import_names:
            raise ImportError()
        return orig_import(name, *args, **kwargs)

    return patch('builtins.__import__', side_effect=mock_import)
