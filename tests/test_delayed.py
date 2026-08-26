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

        shortcircuited = delayed.import_module("blah")
        assert modules["blah"] is shortcircuited, (
            "import_module must return the module if it already is in sys.modules rather than a proxy"
        )


def test_is_delayed():
    d = delayed.regexp("asdf")
    assert delayed.is_delayed(d)
    assert not delayed.is_delayed(re.compile("asdf"))
    assert not delayed.is_delayed(re.Pattern)
    assert not delayed.is_delayed(42)
    assert object.__getattribute__(d, "__obj__") is None
