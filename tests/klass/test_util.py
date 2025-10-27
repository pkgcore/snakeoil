import weakref
from typing import Any

import pytest

from snakeoil.klass.util import combine_classes, get_attrs_of


def test_get_attrs_of():
    def _assert_no_duplicates(obj, **kwds):
        seen = set()
        for k, v in get_attrs_of(obj, **kwds):
            assert k not in seen, "duplicate attributes must not be returned"
            yield k, v
            seen.add(k)

    def assert_attrs(o, result, **kwds):
        assert result == dict(_assert_no_duplicates(o, **kwds))

    def mk_obj(parent=object, slots=None, create=False) -> Any:
        class kls(parent):
            if slots is not None:
                locals()["__slots__"] = (
                    (slots,) if isinstance(slots, str) else tuple(slots)
                )

        if not create:
            return kls
        obj = kls()
        assert_attrs(obj, {})
        return obj

    # make a pure chained slotted class
    obj = mk_obj(mk_obj(slots="x"), "y", create=True)
    obj.x = 1
    assert_attrs(obj, {"x": 1})
    obj.y = 2
    assert_attrs(obj, {"x": 1, "y": 2})
    # verify the reverse direction out of paranoia.
    del obj.x
    assert_attrs(obj, {"y": 2})

    # verify it handles shadowed slots
    obj = mk_obj(mk_obj(slots="x"), slots="x", create=True)  # x is shadowed
    obj.x = 1
    assert_attrs(obj, {"x": 1})

    # ...verify it handles layered __slots__ that normal visibility of the underlying
    # slot, even if it's still a usable attribute
    obj = mk_obj(mk_obj(slots="x"), slots=(), create=True)

    # the fun one.  Mixed slotting.
    obj = mk_obj(mk_obj(), slots="x", create=True)
    obj.x = 1
    assert (
        "x" not in obj.__dict__
    ), "a slotted variable was tucked into __dict__; this is not how python is understood to work for this code.  While real code can do this- it's dumb but possible- this test doesn't do that, thus something is off."
    assert_attrs(obj, {"x": 1})
    obj.y = 2
    assert_attrs(obj, {"x": 1, "y": 2})

    # check weakref and suppression
    obj = mk_obj(create=True)
    ref = weakref.ref(obj)
    assert_attrs(obj, {})

    assert_attrs(obj, {"__weakref__": ref}, weakref=True)
    obj.blah = 1
    assert_attrs(obj, {}, suppressions=["blah"])


def test_combine_classes():
    class kls1(type):
        pass

    class kls2(type):
        pass

    class kls3(type):
        pass

    # assert it requires at least one arg
    pytest.raises(TypeError, combine_classes)

    assert combine_classes(kls1) is kls1, "unneeded derivative metaclass was created"

    # assert that it refuses duplicats
    pytest.raises(TypeError, combine_classes, kls1, kls1)

    # there is caching, thus also do identity check whilst checking the MRO chain
    kls = combine_classes(kls1, kls2, kls3)
    assert (
        kls is combine_classes(kls1, kls2, kls3)
    ), "combine_metaclass uses lru_cache to avoid generating duplicate classes, however this didn't cache"

    combined = combine_classes(kls1, kls2)
    assert [combined, kls1, kls2, type, object] == list(combined.__mro__)
