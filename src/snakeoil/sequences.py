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

from typing import (
    Callable,
    Generic,
    Hashable,
    Iterable,
    Iterator,
    Literal,
    NamedTuple,
    TypeAlias,
    TypeVar,
    overload,
)

from snakeoil._internals import deprecated

from .iterables import expandable_chain

T = TypeVar("T")
H = TypeVar("H", bound=Hashable)


@deprecated(
    """Use set() instead, it will have superior performance characteristics albeit will allocate more than this implementationd which sorted the sequence""",
    removal_in=(0, 12, 0),
)
def unstable_unique(sequence):
    """Given a sequence, return a list of the unique items without preserving ordering."""

    try:
        n = len(sequence)
    except TypeError:
        # if it doesn't support len, assume it's an iterable
        # and fallback to the slower stable_unique
        with deprecated.suppress_deprecations():
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

    u = []
    for x in sequence:
        if x not in u:
            u.append(x)
    return u


@deprecated(
    "Use snakeoil.sequence.unique_stable but be aware it now requires all items be hashable",
    removal_in=(0, 13, 0),
)
def stable_unique(iterable: Iterable[T]) -> list[T]:
    """Given a sequence, return a list of the unique items while preserving ordering.

    For performance reasons, only use this if you really do need to preserve
    the ordering.
    """
    with deprecated.suppress_deprecations():
        return list(iter_stable_unique(iterable))


@deprecated(
    "Use snakeoil.sequence.unique_stable but be aware it now requires all items be hashable",
    removal_in=(0, 13, 0),
)
def iter_stable_unique(iterable: Iterable[T]) -> Iterator[T]:
    """Given a sequence, yield unique items while preserving ordering.

    For performance reasons, only use this if you really do need to preserve
    the ordering.
    """
    seen: set[T] = set()
    unhashable_seen: list[T] = []
    iterable = iter(iterable)
    # the reason for this structuring is purely speed- entering try/except
    # repeatedly is costly, thus structure it to penalize the unhashables
    # instead of penalizing the hashables.
    singleton = object()

    while True:
        x: T = singleton  # pyright: ignore[reportAssignmentType]
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


def unique_stable(iterable: Iterable[H]) -> Iterator[H]:
    """Given an iterator, normalize it yielding items in stable ordering, removing duplicates"""
    s: set[H] = set()
    for thing in iterable:
        if thing not in s:
            yield thing
            s.add(thing)


# in py3.11 it's impossible to represent this recursive typing of iterable, thus
# the typing is wrong.  When py3.12 is the min, change T_recursive to this.
# T_recursive = TypeAliasType("T_recursive", Iterable["T_recursive[T]"] | T, type_params=(T,))
T_recursive: TypeAlias = Iterable[T]


def iflatten_instance(
    iterable: T_recursive, skip_flattening: tuple[type, ...] | type = (str, bytes), /
) -> Iterable[T | str | bytes]:
    """collapse [[1],2] into [1,2]

    :param skip_flattening: list of classes to not descend through
    :return: this generator yields each item that cannot be flattened (or is
        skipped due to being a instance of ``skip_flattening``)
    """

    def f(x):
        # Yes, that logic is weird.  It's historical compatibility that should be ripped out,
        # but exists as a safe  guard since bytes and str being iterable screws up a lot of python
        # code.
        return isinstance(x, skip_flattening) or (
            isinstance(x, (bytes, str)) and len(x) == 1
        )

    return iflatten_func(iterable, f)


# Like iflatten instance, this is impossible to properly type in 3.11
def iflatten_func(
    iterable: T_recursive | T, skip_func: Callable[[T], bool], /
) -> Iterable[T]:
    """collapse [[1],2] into [1,2]

    :param skip_func: a callable that returns True when iflatten_func should
        descend no further
    :return: this generator yields each item that cannot be flattened (or is
        skipped due to a True result from skip_func)
    """
    if skip_func(iterable):  # pyright: ignore[reportArgumentType]
        yield iterable  # pyright: ignore[reportReturnType]
        return
    iters = expandable_chain[T](iterable)  # pyright: ignore[reportArgumentType]
    try:
        while True:
            x = next(iters)
            if hasattr(x, "__iter__") and not skip_func(x):
                iters.appendleft(x)
            else:
                yield x
    except StopIteration:
        pass


T2 = TypeVar("T2")


@overload
def predicate_split(
    func: Callable[[T], bool], stream: Iterable[T], /, key: Literal[None] = None
): ...


@overload
def predicate_split(
    func: Callable[[T2], bool],
    stream: Iterable[T],
    /,
    key: Callable[[T], T2] | None = None,
): ...


def predicate_split(func, stream: Iterable[T], /, key=None) -> tuple[list[T], list[T]]:
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
    stream = iter(stream)
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


class BoolSplitResults(Generic[T], NamedTuple):
    negative: tuple[T]
    positive: tuple[T]


def split_negations(
    iterable: Iterable[str], func: Callable[[str], T] = str
) -> BoolSplitResults[T]:
    """Split an iterable into negative and positive elements.

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
    return BoolSplitResults[T](tuple(neg), tuple(pos))


class BoolTernaryResults(Generic[T], NamedTuple):
    negative: tuple[T]
    neutral: tuple[T]
    positive: tuple[T]


def split_elements(
    iterable: Iterable[str], func: Callable[[str], T] = str
) -> BoolTernaryResults[T]:
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
    return BoolTernaryResults[T](tuple(neg), tuple(neu), tuple(pos))
