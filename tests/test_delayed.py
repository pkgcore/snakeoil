import re

from snakeoil import delayed
from snakeoil.python_namespaces import protect_imports


def test_regexp():
    d = delayed.regexp("aasdf", 1)
    assert re.Pattern is not type(d), "a proxy wasn't returned"
    assert "aasdf" == d.pattern
    assert re.compile("asdf", 1).flags == d.flags
    assert d.match("aasdf")
    assert re.compile("fdas").flags == delayed.regexp("").flags

    # assert we lie.
    assert isinstance(delayed.regexp("asdf"), re.Pattern)


def test_import_module(tmp_path):
    with (tmp_path / "blah.py").open("w") as f:
        f.write("x=1")
    with protect_imports() as (path, modules):
        path.append(str(tmp_path))
        f = delayed.import_module("blah")
        assert "blah" not in modules
        assert "blah" == f.__name__
        assert "blah" in modules
        assert 1 == f.x
        assert modules["blah"] is not f
