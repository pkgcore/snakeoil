# Copyright: 2015 Tim Harder <radhermit@gmail.com>
# License: GPL2/BSD 3 clause

import argparse
from functools import partial
from importlib import reload
import os
import tempfile
from unittest import mock

import pytest

from snakeoil.cli import arghparse
from snakeoil.test import argparse_helpers


class TestArgparseDocs(object):

    def test_add_argument_docs(self):
        # force using an unpatched version of argparse
        reload(argparse)

        parser = argparse.ArgumentParser()
        parser.add_argument('--foo', action='store_true')

        # vanilla argparse doesn't support docs kwargs
        with pytest.raises(TypeError):
            parser.add_argument(
                '-b', '--blah', action='store_true', docs='Blah blah blah')
        with pytest.raises(TypeError):
            parser.add_argument_group('fa', description='fa la la', docs='fa la la la')
        with pytest.raises(TypeError):
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

            assert getattr(parser._subparsers, 'description', None) == expected_txt
            assert getattr(subparser, 'description', None) == expected_txt
            assert getattr(action, 'help', None) == expected_txt
            assert getattr(arg_group, 'description', None) == expected_txt
            assert getattr(mut_action, 'help', None) == expected_txt

        # list/tuple-based docs
        arghparse._generate_docs = True
        docs = 'foo bar'
        parser = argparse.ArgumentParser()
        list_action = parser.add_argument(
            '-b', '--blah', action='store_true', help=default, docs=list(docs.split()))
        tuple_action = parser.add_argument(
            '-c', '--cat', action='store_true', help=default, docs=tuple(docs.split()))
        assert getattr(list_action, 'help', None) == 'foo\nbar'
        assert getattr(tuple_action, 'help', None) == 'foo\nbar'


class BaseArgparseOptions(object):

    def setup_method(self, method):
        self.parser = argparse_helpers.mangle_parser(arghparse.ArgumentParser())


class TestDebugOption(BaseArgparseOptions):

    def test_debug(self):
        namespace = self.parser.parse_args(["--debug"])
        assert namespace.debug
        namespace = self.parser.parse_args([])
        assert not namespace.debug

    def test_debug_disabled(self):
        # ensure the option isn't there if disabled.
        parser = argparse_helpers.mangle_parser(arghparse.ArgumentParser(debug=False))
        namespace = parser.parse_args([])
        assert not hasattr(namespace, 'debug')


class TestStoreBoolAction(BaseArgparseOptions):

    def setup_method(self, method):
        super().setup_method(method)
        self.parser.add_argument("--testing", action=arghparse.StoreBool, default=None)

    def test_bool_disabled(self):
        for raw_val in ("n", "no", "false"):
            for allowed in (raw_val.upper(), raw_val.lower()):
                namespace = self.parser.parse_args(['--testing=' + allowed])
                assert not namespace.testing

    def test_bool_enabled(self):
        for raw_val in ("y", "yes", "true"):
            for allowed in (raw_val.upper(), raw_val.lower()):
                namespace = self.parser.parse_args(['--testing=' + allowed])
                assert namespace.testing

    def test_bool_invalid(self):
        with pytest.raises(argparse_helpers.Error):
            self.parser.parse_args(["--testing=invalid"])


class TestExtendCommaDelimitedAction(BaseArgparseOptions):

    def test_parse_args(self):
        self.parser.add_argument('--testing', action='extend_comma')
        self.parser.add_argument('--testing-nargs', nargs='+', action='extend_comma')

        test_values = (
            ('', []),
            (',', []),
            (',,', []),
            ('a', ['a']),
            ('a,b,-c', ['a', 'b', '-c']),
        )
        for raw_val, expected in test_values:
            namespace = self.parser.parse_args([
                '--testing=' + raw_val,
                '--testing-nargs', raw_val, raw_val,
                ])
            assert namespace.testing == expected
            assert namespace.testing_nargs == expected * 2


class TestExtendCommaDelimitedToggleAction(BaseArgparseOptions):

    def test_parse_args(self):
        self.parser.add_argument('--testing', action='extend_comma_toggle')
        self.parser.add_argument('--testing-nargs', nargs='+', action='extend_comma_toggle')

        test_values = (
            ('', ([], [])),
            (',', ([], [])),
            (',,', ([], [])),
            ('a', ([], ['a'])),
            ('a,-b,-c,d', (['b', 'c'], ['a', 'd'])),
        )
        for raw_val, expected in test_values:
            namespace = self.parser.parse_args([
                '--testing=' + raw_val,
                '--testing-nargs', raw_val, raw_val,
                ])
            assert namespace.testing == expected
            assert namespace.testing_nargs == (expected[0] * 2, expected[1] * 2)

        # start with negated arg
        namespace = self.parser.parse_args(['--testing=-a'])
        assert namespace.testing == (['a'], [])


class TestExistentPathType(BaseArgparseOptions):

    def setup_method(self, method):
        super().setup_method(method)
        self.parser.add_argument('--path', type=arghparse.existent_path)

    def test_nonexistent(self):
        # nonexistent path arg raises an error
        with pytest.raises(argparse_helpers.Error):
            self.parser.parse_args(['--path=/path/to/nowhere'])

    def test_os_errors(self, tmpdir):
        # random OS/FS issues raise errors
        with mock.patch('snakeoil.osutils.abspath') as abspath:
            abspath.side_effect = OSError(19, 'Random OS error')
            with pytest.raises(argparse_helpers.Error):
                self.parser.parse_args(['--path=%s' % tmpdir])

    def test_regular_usage(self, tmpdir):
        namespace = self.parser.parse_args(['--path=%s' % tmpdir])
        assert namespace.path == str(tmpdir)


class TestNamespace(object):

    def setup_method(self, method):
        self.parser = argparse_helpers.mangle_parser(arghparse.ArgumentParser())

    def test_pop(self):
        self.parser.set_defaults(test=True)
        namespace = self.parser.parse_args([])
        assert namespace.pop('test') == True

        # re-popping raises an exception since the attr has been removed
        with pytest.raises(AttributeError):
            namespace.pop('test')

        # popping a nonexistent attr with a fallback returns the fallback
        assert namespace.pop('nonexistent', 'foo') == 'foo'

    def test_collapse_delayed(self):
        def _delayed_val(namespace, attr, val):
            setattr(namespace, attr, val)
        self.parser.set_defaults(delayed=arghparse.DelayedValue(partial(_delayed_val, val=42)))
        namespace = self.parser.parse_args([])
        assert namespace.delayed == 42
