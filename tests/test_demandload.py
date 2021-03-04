import sre_constants

import pytest

from snakeoil import demandload

# few notes:
# all tests need to be wrapped w/ the following decorator; it
# ensures that snakeoils env-aware disabling is reversed, ensuring the
# setup is what the test expects.
# it also explicitly resets the state on the way out.

def reset_globals(functor):
    def f(*args, **kwds):
        orig_demandload = demandload.demandload
        orig_demand_compile = demandload.demand_compile_regexp
        orig_protection = demandload._protection_enabled
        orig_noisy = demandload._noisy_protection
        try:
            return functor(*args, **kwds)
        finally:
            demandload.demandload = orig_demandload
            demandload.demand_compile_regexp = orig_demand_compile
            demandload._protection_enabled = orig_protection
            demandload._noisy_protection = orig_noisy
    return f


class TestParser:

    @reset_globals
    def test_parse(self):
        for input, output in [
                ('foo', [('foo', 'foo')]),
                ('foo:bar', [('foo.bar', 'bar')]),
                ('foo:bar,baz@spork', [('foo.bar', 'bar'), ('foo.baz', 'spork')]),
                ('foo@bar', [('foo', 'bar')]),
                ('foo_bar', [('foo_bar', 'foo_bar')]),
            ]:
            assert output == list(demandload.parse_imports([input]))
        pytest.raises(ValueError, list, demandload.parse_imports(['a.b']))
        pytest.raises(ValueError, list, demandload.parse_imports(['a:,']))
        pytest.raises(ValueError, list, demandload.parse_imports(['a:b,x@']))
        pytest.raises(ValueError, list, demandload.parse_imports(['b-x']))
        pytest.raises(ValueError, list, demandload.parse_imports([' b_x']))


class TestPlaceholder:

    @reset_globals
    def test_getattr(self):
        scope = {}
        placeholder = demandload.Placeholder(scope, 'foo', list)
        assert scope == object.__getattribute__(placeholder, '_scope')
        assert placeholder.__doc__ == [].__doc__
        assert scope['foo'] == []
        demandload._protection_enabled = lambda: True
        with pytest.raises(ValueError):
            getattr(placeholder, '__doc__')

    @reset_globals
    def test__str__(self):
        scope = {}
        placeholder = demandload.Placeholder(scope, 'foo', list)
        assert scope == object.__getattribute__(placeholder, '_scope')
        assert str(placeholder) == str([])
        assert scope['foo'] == []

    @reset_globals
    def test_call(self):
        def passthrough(*args, **kwargs):
            return args, kwargs
        def get_func():
            return passthrough
        scope = {}
        placeholder = demandload.Placeholder(scope, 'foo', get_func)
        assert scope == object.__getattribute__(placeholder, '_scope')
        assert (('arg',), {'kwarg': 42}) == placeholder('arg', kwarg=42)
        assert passthrough is scope['foo']

    @reset_globals
    def test_setattr(self):
        class Struct:
            pass

        scope = {}
        placeholder = demandload.Placeholder(scope, 'foo', Struct)
        placeholder.val = 7
        demandload._protection_enabled = lambda: True
        with pytest.raises(ValueError):
            getattr(placeholder, 'val')
        assert 7 == scope['foo'].val


class TestImport:

    @reset_globals
    def test_demandload(self):
        scope = {}
        demandload.demandload('snakeoil:demandload', scope=scope)
        assert demandload is not scope['demandload']
        assert demandload.demandload is scope['demandload'].demandload
        assert demandload is scope['demandload']

    @reset_globals
    def test_disabled_demandload(self):
        scope = {}
        demandload.disabled_demandload('snakeoil:demandload', scope=scope)
        assert demandload is scope['demandload']


class TestDemandCompileRegexp:

    @reset_globals
    def test_demand_compile_regexp(self):
        scope = {}
        demandload.demand_compile_regexp('foo', 'frob', scope=scope)
        assert list(scope.keys()) == ['foo']
        assert 'frob' == scope['foo'].pattern
        assert 'frob' == scope['foo'].pattern

        # verify it's delayed via a bad regex.
        demandload.demand_compile_regexp('foo', 'f(', scope=scope)
        assert list(scope.keys()) == ['foo']
        # should blow up on accessing an attribute.
        obj = scope['foo']
        with pytest.raises(sre_constants.error):
            getattr(obj, 'pattern')
