import sys
import traceback


def walk_exception_chain(exc, ignore_first=False, reverse=False):
    l = _inner_walk_exception_chain(exc, ignore_first)
    if reverse:
        l = reversed(list(l))
    return l


def _inner_walk_exception_chain(exc, ignore_first):
    if not ignore_first:
        yield exc
    exc = getattr(exc, '__cause__', None)
    while exc is not None:
        yield exc
        exc = getattr(exc, '__cause__', None)


def dump_error(raw_exc, msg=None, handle=sys.stderr, tb=None):
    # force default output for exceptions
    if getattr(handle, 'reset', False):
        handle.write(handle.reset)

    prefix = ''
    if msg:
        prefix = ' '
        handle.write(msg.rstrip("\n") + ":\n")
        if tb:
            handle.write("Traceback follows:\n")
            traceback.print_tb(tb, file=handle)
    exc_strings = []
    if raw_exc is not None:
        for exc in walk_exception_chain(raw_exc):
            exc_strings.extend(
                '%s%s' % (prefix, x.strip())
                for x in (x for x in str(exc).split("\n") if x))
    if exc_strings:
        if msg and tb:
            handle.write("\n%s:\n" % raw_exc.__class__.__name__)
        handle.write("\n".join(exc_strings))
        handle.write("\n")
