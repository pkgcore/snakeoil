# Copyright: 2015 Tim Harder <radhermit@gmail.com>
# License: GPL2/BSD 3 clause

import argparse
from unittest import TestCase

try:
    # py3.4 and up
    from importlib import reload
except ImportError:
    # py2
    pass

from snakeoil.cli import arghparse
from snakeoil.test import argparse_helpers


class TestArgparseDocs(TestCase):

    def test_add_argument_docs(self):
        # force using an unpatched version of argparse
        reload(argparse)

        parser = argparse.ArgumentParser()
        parser.add_argument('--foo', action='store_true')

        # vanilla argparse doesn't support docs kwargs
        with self.assertRaises(TypeError):
            parser.add_argument(
                '-b', '--blah', action='store_true', docs='Blah blah blah')
        with self.assertRaises(TypeError):
            parser.add_argument_group('fa', description='fa la la', docs='fa la la la')
        with self.assertRaises(TypeError):
            parser.add_mutually_exclusive_group('fee', description='fi', docs='fo fum')

        # forcibly monkey-patch argparse to allow docs kwargs
        reload(arghparse)

        default = 'baz baz'
        docs = 'blah blah'
        for enable_docs, expected_txt in ((False, default), (True, docs)):
            arghparse._generate_docs = enable_docs
            parser = argparse.ArgumentParser()
            subparsers = parser.add_subparsers(description=default, docs=docs)
            subparser = subparsers.add_parser('foo', description=default, docs=docs)
            action = parser.add_argument(
                '-b', '--blah', action='store_true', help=default, docs=docs)
            arg_group = parser.add_argument_group('fa', description=default, docs=docs)
            mut_arg_group = parser.add_mutually_exclusive_group()
            mut_action = mut_arg_group.add_argument(
                '-f', '--fee', action='store_true', help=default, docs=docs)

            self.assertEqual(getattr(parser._subparsers, 'description', None), expected_txt)
            self.assertEqual(getattr(subparser, 'description', None), expected_txt)
            self.assertEqual(getattr(action, 'help', None), expected_txt)
            self.assertEqual(getattr(arg_group, 'description', None), expected_txt)
            self.assertEqual(getattr(mut_action, 'help', None), expected_txt)

        # list/tuple-based docs
        arghparse._generate_docs = True
        docs = 'foo bar'
        parser = argparse.ArgumentParser()
        list_action = parser.add_argument(
            '-b', '--blah', action='store_true', help=default, docs=list(docs.split()))
        tuple_action = parser.add_argument(
            '-c', '--cat', action='store_true', help=default, docs=tuple(docs.split()))
        self.assertEqual(getattr(list_action, 'help', None), 'foo\nbar')
        self.assertEqual(getattr(tuple_action, 'help', None), 'foo\nbar')


class ArgparseOptionsTest(TestCase):

    def _parser(self, **kwargs):
        return arghparse.ArgumentParser(**kwargs)

    def test_debug(self):
        namespace = self._parser().parse_args(["--debug"])
        self.assertTrue(namespace.debug)
        namespace = self._parser().parse_args([])
        self.assertFalse(namespace.debug)

        # ensure the option isn't there if disabled.
        namespace = self._parser(debug=False).parse_args([])
        self.assertFalse(hasattr(namespace, 'debug'))

    def test_bool_type(self):
        parser = argparse_helpers.mangle_parser(arghparse.ArgumentParser())
        parser.add_argument(
            "--testing", action=arghparse.StoreBool, default=None)

        for raw_val in ("n", "no", "false"):
            for allowed in (raw_val.upper(), raw_val.lower()):
                namespace = parser.parse_args(['--testing=' + allowed])
                self.assertEqual(
                    namespace.testing, False,
                    msg="for --testing=%s, got %r, expected False" %
                        (allowed, namespace.testing))

        for raw_val in ("y", "yes", "true"):
            for allowed in (raw_val.upper(), raw_val.lower()):
                namespace = parser.parse_args(['--testing=' + allowed])
                self.assertEqual(
                    namespace.testing, True,
                    msg="for --testing=%s, got %r, expected False" %
                        (allowed, namespace.testing))

        try:
            parser.parse_args(["--testing=invalid"])
        except argparse_helpers.Error:
            pass
        else:
            self.fail("no error message thrown for --testing=invalid")

    def test_extend_comma_action(self):
        parser = argparse_helpers.mangle_parser(arghparse.ArgumentParser())
        parser.add_argument('--testing', action='extend_comma')
        parser.add_argument('--testing-nargs', nargs='+', action='extend_comma')

        test_values = (
            ('', []),
            (',', []),
            (',,', []),
            ('a', ['a']),
            ('a,b,-c', ['a', 'b', '-c']),
        )
        for raw_val, expected in test_values:
            namespace = parser.parse_args([
                '--testing=' + raw_val,
                '--testing-nargs', raw_val, raw_val,
                ])
            self.assertEqual(namespace.testing, expected)
            self.assertEqual(namespace.testing_nargs, expected * 2)

    def test_extend_comma_toggle_action(self):
        parser = argparse_helpers.mangle_parser(arghparse.ArgumentParser())
        parser.add_argument('--testing', action='extend_comma_toggle')
        parser.add_argument('--testing-nargs', nargs='+', action='extend_comma_toggle')

        test_values = (
            ('', ([], [])),
            (',', ([], [])),
            (',,', ([], [])),
            ('a', ([], ['a'])),
            ('a,-b,-c,d', (['b', 'c'], ['a', 'd'])),
        )
        for raw_val, expected in test_values:
            namespace = parser.parse_args([
                '--testing=' + raw_val,
                '--testing-nargs', raw_val, raw_val,
                ])
            self.assertEqual(namespace.testing, expected)
            self.assertEqual(namespace.testing_nargs, (expected[0] * 2, expected[1] * 2))

        # start with negated arg
        namespace = parser.parse_args(['--testing=-a'])
        self.assertEqual(namespace.testing, (['a'], []))
