"""Various decorator utilities."""

from functools import wraps


def coroutine(func):
    """Prime a coroutine for input."""

    @wraps(func)
    def prime(*args, **kwargs):
        cr = func(*args, **kwargs)
        next(cr)
        return cr

    return prime
