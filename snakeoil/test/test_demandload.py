# Copyright: 2007 - 2015 Brian Harring <ferringb@gmail.com>
# Copyright: 2007 Marien Zwart <marienz@gentoo.org>
# License: BSD/GPL2


import sre_constants

from snakeoil.test import TestCase
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


class ParserTest(TestCase):

    @reset_globals
    def test_parse(self):
        for input, output in [
                ('foo', [('foo', 'foo')]),
                ('foo:bar', [('foo.bar', 'bar')]),
                ('foo:bar,baz@spork', [('foo.bar', 'bar'), ('foo.baz', 'spork')]),
                ('foo@bar', [('foo', 'bar')]),
                ('foo_bar', [('foo_bar', 'foo_bar')]),
            ]:
            self.assertEqual(output, list(demandload.parse_imports([input])))
        self.assertRaises(ValueError, list, demandload.parse_imports(['a.b']))
        self.assertRaises(ValueError, list, demandload.parse_imports(['a:,']))
        self.assertRaises(ValueError, list, demandload.parse_imports(['a:b,x@']))
        self.assertRaises(ValueError, list, demandload.parse_imports(['b-x']))
        self.assertRaises(ValueError, list, demandload.parse_imports([' b_x']))


class PlaceholderTest(TestCase):

    @reset_globals
    def test_getattr(self):
        scope = {}
        placeholder = demandload.Placeholder(scope, 'foo', list)
        self.assertEqual(scope, object.__getattribute__(placeholder, '_scope'))
        self.assertEqual(placeholder.__doc__, [].__doc__)
        self.assertEqual(scope['foo'], [])
        demandload._protection_enabled = lambda: True
        self.assertRaises(ValueError, getattr, placeholder, '__doc__')

    @reset_globals
    def test__str__(self):
        scope = {}
        placeholder = demandload.Placeholder(scope, 'foo', list)
        self.assertEqual(scope, object.__getattribute__(placeholder, '_scope'))
        self.assertEqual(str(placeholder), str([]))
        self.assertEqual(scope['foo'], [])

    @reset_globals
    def test_call(self):
        def passthrough(*args, **kwargs):
            return args, kwargs
        def get_func():
            return passthrough
        scope = {}
        placeholder = demandload.Placeholder(scope, 'foo', get_func)
        self.assertEqual(scope, object.__getattribute__(placeholder, '_scope'))
        self.assertEqual(
            (('arg',), {'kwarg': 42}), placeholder('arg', kwarg=42))
        self.assertIdentical(passthrough, scope['foo'])

    @reset_globals
    def test_setattr(self):
        class Struct(object):
            pass

        scope = {}
        placeholder = demandload.Placeholder(scope, 'foo', Struct)
        placeholder.val = 7
        demandload._protection_enabled = lambda: True
        self.assertRaises(ValueError, getattr, placeholder, 'val')
        self.assertEqual(7, scope['foo'].val)


class ImportTest(TestCase):

    @reset_globals
    def test_demandload(self):
        scope = {}
        demandload.demandload('snakeoil:demandload', scope=scope)
        self.assertNotIdentical(demandload, scope['demandload'])
        self.assertIdentical(
            demandload.demandload, scope['demandload'].demandload)
        self.assertIdentical(demandload, scope['demandload'])

    @reset_globals
    def test_disabled_demandload(self):
        scope = {}
        demandload.disabled_demandload('snakeoil:demandload', scope=scope)
        self.assertIdentical(demandload, scope['demandload'])


class DemandCompileRegexpTest(TestCase):

    @reset_globals
    def test_demand_compile_regexp(self):
        scope = {}
        demandload.demand_compile_regexp('foo', 'frob', scope=scope)
        self.assertEqual(scope.keys(), ['foo'])
        self.assertEqual('frob', scope['foo'].pattern)
        self.assertEqual('frob', scope['foo'].pattern)

        # verify it's delayed via a bad regex.
        demandload.demand_compile_regexp('foo', 'f(', scope=scope)
        self.assertEqual(scope.keys(), ['foo'])
        # should blow up on accessing an attribute.
        obj = scope['foo']
        self.assertRaises(sre_constants.error, getattr, obj, 'pattern')
