"""Various decorator utilities."""

from functools import wraps

from .contexts import SplitExec, Namespace


def splitexec(func):
    """Run the decorated function in another process."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        with SplitExec():
            return func(*args, **kwargs)
    return wrapper


def namespace(**namespaces):
    """Run the decorated function in a specified namespace."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with Namespace(**namespaces):
                return func(*args, **kwargs)
        return wrapper
    return decorator


def coroutine(func):
    """Prime a coroutine for input."""
    @wraps(func)
    def prime(*args, **kwargs):
        cr = func(*args, **kwargs)
        next(cr)
        return cr
    return prime
