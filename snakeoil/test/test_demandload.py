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
            return f(*args, **kwds)
        finally:
            demandload.demandload = orig_demandload
            demandload.demand_compile_regexp = orig_demand_compile
            demandload._protection_enabled = orig_protection
            demandload._noisy_protection = orig_noisy


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
        placeholder = demandload.Placeholder('foo', list)
        self.assertEqual(globals(), placeholder._scope)
        self.assertEqual(placeholder.__doc__, [].__doc__)
        self.assertEqual(globals['foo'], [])
        demandload._protection_enabled = lambda: True
        self.assertRaises(ValueError, getattr, placeholder, '__doc__')

    @reset_globals
    def test__str__(self):
        placeholder = demandload.Placeholder('foo', list)
        self.assertEqual(globals(), placeholder._scope)
        self.assertEqual(str(placeholder), str([]))
        self.assertEqual(globals()['foo'], [])

    @reset_globals
    def test_call(self):
        def passthrough(*args, **kwargs):
            return args, kwargs
        def get_func():
            return passthrough
        placeholder = demandload.Placeholder('foo', get_func)
        self.assertEqual(globals(), placeholder._scope)
        self.assertEqual(
            (('arg',), {'kwarg': 42}), placeholder('arg', kwarg=42))
        self.assertIdentical(passthrough, globals()['foo'])

    @reset_globals
    def test_setattr(self):
        class Struct(object):
            pass

        placeholder = demandload.Placeholder('foo', Struct)
        placeholder.val = 7
        demandload._protection_enabled = lambda: True
        self.assertRaises(ValueError, getattr, placeholder, 'val')
        self.assertEqual(7, globals()['foo'].val)


class ImportTest(TestCase):

    @reset_globals
    def test_demandload(self):
        demandload.demandload('snakeoil:demandload')
        self.assertNotIdentical(demandload, globals()['demandload'])
        self.assertIdentical(
            demandload.demandload, globals()['demandload'].demandload)
        self.assertIdentical(demandload, globals()['demandload'])

    @reset_globals
    def test_disabled_demandload(self):
        demandload.disabled_demandload('snakeoil:demandload')
        self.assertIdentical(demandload, globals()['demandload'])


class DemandCompileRegexpTest(TestCase):

    @reset_globals
    def test_demand_compile_regexp(self):
        demandload.demand_compile_regexp('foo', 'frob')
        self.assertEqual(globals().keys(), ['foo'])
        self.assertEqual('frob', globals()['foo'].pattern)
        self.assertEqual('frob', globals()['foo'].pattern)

        # verify it's delayed via a bad regex.
        demandload.demand_compile_regexp('foo', 'f(')
        self.assertEqual(globals().keys(), ['foo'])
        # should blow up on accessing an attribute.
        obj = globals()['foo']
        self.assertRaises(sre_constants.error, getattr, obj, 'pattern')
