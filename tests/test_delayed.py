import re

from snakeoil import delayed


def test_regexp():
    d = delayed.regexp("aasdf", 1)
    assert re.Pattern is not type(d), "a proxy wasn't returned"
    assert "aasdf" == d.pattern
    assert re.compile("asdf", 1).flags == d.flags
    assert d.match("aasdf")
    assert re.compile("fdas").flags == delayed.regexp("").flags

    # assert we lie.
    assert isinstance(delayed.regexp("asdf"), re.Pattern)
