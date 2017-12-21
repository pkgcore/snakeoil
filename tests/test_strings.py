# Copyright: 2017 Tim Harder <radhermit@gmail.com>
# License: BSD/GPL2

from snakeoil.strings import pluralism


def test_none():
    # default
    assert pluralism([]) == 's'

    # different suffix for nonexistence
    assert pluralism([], none='') == ''

def test_singular():
    # default
    assert pluralism([1]) == ''

    # different suffix for singular existence
    assert pluralism([1], singular='o') == 'o'

def test_plural():
    # default
    assert pluralism([1, 2]) == 's'

    # different suffix for plural existence
    assert pluralism([1, 2], plural='ies') == 'ies'

def test_int():
    assert pluralism(0) == 's'
    assert pluralism(1) == ''
    assert pluralism(2) == 's'
