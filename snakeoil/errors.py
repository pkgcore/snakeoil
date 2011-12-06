# Copyright: 2011 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD 3 clause

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
