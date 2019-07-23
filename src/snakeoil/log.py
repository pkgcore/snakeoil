"""Logging utilities."""

from contextlib import contextmanager
import logging

from . import __title__


# The logging system will call this automagically if its module-level logging
# functions are used. We call it explicitly to make sure something handles
# messages sent to our non-root logger. If the root logger already has handlers
# this is a noop, and if someone attaches a handler to our logger that
# overrides the root logger handler.
logging.basicConfig()

# Our main logger.
logger = logging.getLogger(__title__)


@contextmanager
def suppress_logging(level=logging.CRITICAL):
    """Context manager to suppress logging messages.

    :param level: logging level and below to suppress
    """
    orig_level = logging.root.manager.disable
    logging.disable(level)
    try:
        yield
    finally:
        logging.disable(orig_level)
