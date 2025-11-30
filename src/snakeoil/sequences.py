"""sequence related operations and classes"""

__all__ = (
    "unstable_unique",
    "stable_unique",
    "iter_stable_unique",
    "iflatten_instance",
    "iflatten_func",
    "predicate_split",
    "split_negations",
    "split_elements",
)

from typing import Any, Callable, Iterable, Type

from .iterables import expandable_chain


def unstable_unique(sequence):
    """Given a sequence, return a list of the unique items without preserving ordering."""

    try:
        n = len(sequence)
    except TypeError:
        # if it doesn't support len, assume it's an iterable
        # and fallback to the slower stable_unique
        return stable_unique(sequence)
    # assume all elements are hashable, if so, it's linear
    try:
        return list(set(sequence))
    except TypeError:
        pass

    # so much for linear.  abuse sort.
    try:
        t = sorted(sequence)
    except TypeError:
        pass
    else:
        assert n > 0
        last = t[0]
        lasti = i = 1
        while i < n:
            if t[i] != last:
                t[lasti] = last = t[i]
                lasti += 1
            i += 1
        return t[:lasti]

    # blah.  back to original portage.unique_array
    u = []
    for x in sequence:
        if x not in u:
            u.append(x)
    return u


def stable_unique(iterable):
    """Given a sequence, return a list of the unique items while preserving ordering.

    For performance reasons, only use this if you really do need to preserve
    the ordering.
    """
    return list(iter_stable_unique(iterable))


def iter_stable_unique(iterable):
    """Given a sequence, yield unique items while preserving ordering.

    For performance reasons, only use this if you really do need to preserve
    the ordering.
    """
    seen = set()
    unhashable_seen = []
    iterable = iter(iterable)
    # the reason for this structuring is purely speed- entering try/except
    # repeatedly is costly, thus structure it to penalize the unhashables
    # instead of penalizing the hashables.
    singleton = object()

    while True:
        x = singleton
        try:
            for x in iterable:
                if x not in seen:
                    yield x
                    seen.add(x)
        except TypeError:
            # unhashable item pathway
            if x is singleton:
                # the iterable itself threw the TypeError
                raise
            if x not in unhashable_seen:
                yield x
                unhashable_seen.append(x)
            continue
        break


def iflatten_instance(
    l: Iterable, skip_flattening: Iterable[Type] = (str, bytes)
) -> Iterable:
    """collapse [[1],2] into [1,2]

    :param skip_flattening: list of classes to not descend through
    :return: this generator yields each item that cannot be flattened (or is
        skipped due to being a instance of ``skip_flattening``)
    """
    if isinstance(l, skip_flattening):
        yield l
        return
    iters = expandable_chain(l)
    try:
        while True:
            x = next(iters)
            if hasattr(x, "__iter__") and not (
                isinstance(x, skip_flattening)
                or (isinstance(x, (str, bytes)) and len(x) == 1)
            ):
                iters.appendleft(x)
            else:
                yield x
    except StopIteration:
        pass


def iflatten_func(l: Iterable, skip_func: Callable[[Any], bool]) -> Iterable:
    """collapse [[1],2] into [1,2]

    :param skip_func: a callable that returns True when iflatten_func should
        descend no further
    :return: this generator yields each item that cannot be flattened (or is
        skipped due to a True result from skip_func)
    """
    if skip_func(l):
        yield l
        return
    iters = expandable_chain(l)
    try:
        while True:
            x = next(iters)
            if hasattr(x, "__iter__") and not skip_func(x):
                iters.appendleft(x)
            else:
                yield x
    except StopIteration:
        pass


def predicate_split(func, stream, key=None):
    """
    Given a stream and a function, split the stream into two sequences based on
    the results of the func for that item

    :param func: function to invoke with the item; function must return True or False
    :param stream: iterable to split into two sequences
    :param key: if set, a function to use to pull the attribute to inspect.  Basically
        the same sort of trick as the key paramater for :py:func:`sorted`
    :return: two lists, the first a list of everything that was False, the second a
        list of everything that was True

    Example usage:

    >>> from snakeoil.sequences import predicate_split
    >>> odd, even = predicate_split(lambda x:x % 2 == 0, range(10))
    >>> assert odd == [1, 3, 5, 7, 9]
    >>> assert even == [0, 2, 4, 6, 8]
    """
    true_l, false_l = [], []
    tappend, fappend = true_l.append, false_l.append
    # needs to be fast... this this since a simple
    # lambda x:x # is a bit more of a killer then you would think.
    if key is not None:
        for item in stream:
            if func(key(item)):
                tappend(item)
            else:
                fappend(item)
    else:
        for item in stream:
            if func(item):
                tappend(item)
            else:
                fappend(item)
    return false_l, true_l


def split_negations(iterable, func=str):
    """ "Split an iterable into negative and positive elements.

    :param iterable: iterable targeted for splitting
    :param func: wrapper method to modify tokens

    :return: Tuple containing negative and positive element tuples, respectively.
    """
    neg, pos = [], []
    for token in iterable:
        if token[0] == "-":
            if len(token) == 1:
                raise ValueError("'-' negation without a token")
            token = token[1:]
            l = neg
        else:
            l = pos
        obj = func(token)
        if obj is not None:
            l.append(obj)
    return tuple(neg), tuple(pos)


def split_elements(iterable, func=str):
    """ "Split an iterable into negative, neutral, and positive elements.

    :param iterable: iterable targeted for splitting
    :param func: wrapper method to modify tokens

    :return: Tuple containing negative, neutral, and positive element tuples, respectively.
    """
    neg, neu, pos = [], [], []
    token_map = {"-": neg, "+": pos}
    for token in iterable:
        if token[0] in token_map:
            if len(token) == 1:
                raise ValueError("%r without a token" % (token[0],))
            l = token_map[token[0]]
            token = token[1:]
        else:
            l = neu
        obj = func(token)
        if obj is not None:
            l.append(obj)
    return tuple(neg), tuple(neu), tuple(pos)
