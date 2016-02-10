# Copyright: 2010 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD 3 clause

from operator import itemgetter

# pylint: disable=wildcard-import,unused-wildcard-import
from snakeoil.lists import *


class base_namedtuple(tuple):

    __slots__ = ()
    _fields = ()

    def __new__(cls, *values):
        return super(base_namedtuple, cls).__new__(cls, values)


def namedtuple(typename, field_names):
    """Returns a new subclass of tuple with named fields.

    while collections.namedtuple exists... it's fairly heavy and nasty in innards.

    We choose to use a simpler version.
    """

    class kls(base_namedtuple):
        __slots__ = ()
        _fields = tuple(field_names)

        locals().update((k, property(itemgetter(idx)))
                        for idx, k in enumerate(field_names))

    kls.__name__ = typename
    return kls


def split_negations(data, func=str):
    """"Split a sequence into negative and positive elements."""
    neg, pos = [], []
    for line in data:
        if line[0] == '-':
            if len(line) == 1:
                raise ValueError("'-' negation without a token")
            neg.append(func(line[1:]))
        else:
            pos.append(func(line))
    return (tuple(neg), tuple(pos))
