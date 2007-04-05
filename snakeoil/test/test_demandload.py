# Copyright: 2007 Marien Zwart <marienz@gentoo.org>
# License: GPL2


from snakeoil.test import TestCase
from snakeoil import demandload


class ParserTest(TestCase):

    def test_parse(self):
        for input, output in [
            ('foo', [('foo', 'foo')]),
            ('foo:bar', [('foo.bar', 'bar')]),
            ('foo:bar,baz@spork', [('foo.bar', 'bar'), ('foo.baz', 'spork')]),
            ('foo@bar', [('foo', 'bar')]),
            ]:
            self.assertEqual(output, list(demandload.parse_imports([input])))
        self.assertRaises(ValueError, list, demandload.parse_imports(['a.b']))


class PlaceholderTest(TestCase):

    def test_getattr(self):
        scope = {}
        placeholder = demandload.Placeholder(scope, 'foo', list)
        self.assertEqual({}, scope)
        self.assertEqual(placeholder.__doc__, [].__doc__)
        self.assertEqual(scope['foo'], [])
        self.assertRaises(ValueError, getattr, placeholder, '__doc__')

    def test_call(self):
        def passthrough(*args, **kwargs):
            return args, kwargs
        def get_func():
            return passthrough
        scope = {}
        placeholder = demandload.Placeholder(scope, 'foo', get_func)
        self.assertEqual({}, scope)
        self.assertEqual(
            (('arg',), {'kwarg': 42}), placeholder('arg', kwarg=42))
        self.assertIdentical(passthrough, scope['foo'])

    def test_setattr(self):
        class Struct(object):
            pass

        scope = {}
        placeholder = demandload.Placeholder(scope, 'foo', Struct)
        placeholder.val = 7
        self.assertRaises(ValueError, getattr, placeholder, 'val')
        self.assertEqual(7, scope['foo'].val)


class ImportTest(TestCase):

    def test_demandload(self):
        scope = {}
        demandload.demandload(scope, 'snakeoil:demandload')
        self.assertNotIdentical(demandload, scope['demandload'])
        self.assertIdentical(
            demandload.demandload, scope['demandload'].demandload)
        self.assertIdentical(demandload, scope['demandload'])

    def test_disabled_demandload(self):
        scope = {}
        demandload.disabled_demandload(scope, 'snakeoil:demandload')
        self.assertIdentical(demandload, scope['demandload'])


class DemandCompileRegexpTest(TestCase):

    def test_demand_compile_regexp(self):
        scope = {}
        placeholder = demandload.demand_compile_regexp(scope, 'foo', 'frob')
        self.assertEqual({}, scope)
        self.assertEqual('frob', placeholder.pattern)
        self.assertEqual('frob', scope['foo'].pattern)
