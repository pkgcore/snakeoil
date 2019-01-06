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
        assert namespace.debug is True
        namespace = self.parser.parse_args([])
        assert namespace.debug is False

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
                assert namespace.testing is False

    def test_bool_enabled(self):
        for raw_val in ("y", "yes", "true"):
            for allowed in (raw_val.upper(), raw_val.lower()):
                namespace = self.parser.parse_args(['--testing=' + allowed])
                assert namespace.testing is True

    def test_bool_invalid(self):
        with pytest.raises(argparse_helpers.Error):
            self.parser.parse_args(["--testing=invalid"])


class ParseStdinTest(BaseArgparseOptions):

    def setup_method(self, method, allow_stdin):
        super().setup_method(method)
        self.parser.add_argument(
            "testing", nargs='+', allow_stdin=allow_stdin, action=arghparse.ParseStdin)

    def test_none_invalid(self):
        with pytest.raises(argparse_helpers.Error):
            self.parser.parse_args([])

    def test_non_stdin(self):
        namespace = self.parser.parse_args(['foo'])
        assert namespace.testing == ['foo']

    def test_non_stdin_multiple(self):
        namespace = self.parser.parse_args(['foo', 'bar'])
        assert namespace.testing == ['foo', 'bar']

    def test_stdin(self):
        namespace = self.parser.parse_args(['-'])
        assert namespace.testing == ['-']


class TestParseStdinDisabled(ParseStdinTest):

    def setup_method(self, method):
        super().setup_method(method, allow_stdin=False)


class TestParseStdinEnabled(ParseStdinTest):

    def setup_method(self, method):
        super().setup_method(method, allow_stdin=True)

    def test_stdin(self):
        # stdin is an interactive tty
        with mock.patch('sys.stdin.isatty', return_value=True):
            with pytest.raises(argparse_helpers.Error) as excinfo:
                namespace = self.parser.parse_args(['-'])
            assert 'only valid when piping data in' in str(excinfo.value)

        # fake piping data in
        for readlines, expected in (
                ([], []),
                ([' '], []),
                (['\n'], []),
                (['\n', '\n'], []),
                (['foo'], ['foo']),
                (['foo '], ['foo']),
                (['foo\n'], ['foo']),
                (['foo', 'bar', 'baz'], ['foo', 'bar', 'baz']),
                (['\nfoo\n', ' bar ', '\nbaz'], ['foo', 'bar', 'baz']),
        ):
            with mock.patch('sys.stdin') as stdin, \
                    mock.patch("builtins.open", mock.mock_open()) as mock_file:
                stdin.readlines.return_value = readlines
                stdin.isatty.return_value = False
                namespace = self.parser.parse_args(['-'])
                mock_file.assert_called_once_with("/dev/tty")
            assert namespace.testing == expected


class TestCommaSeparatedValuesAction(BaseArgparseOptions):

    def setup_method(self, method):
        super().setup_method(method)
        self.test_values = (
            ('', []),
            (',', []),
            (',,', []),
            ('a', ['a']),
            ('a,b,-c', ['a', 'b', '-c']),
        )

        self.action = 'csv'
        self.single_expected = lambda x: x
        self.multi_expected = lambda x: x

    def test_parse_args(self):
        self.parser.add_argument('--testing', action=self.action)
        for raw_val, expected in self.test_values:
            namespace = self.parser.parse_args(['--testing=' + raw_val])
            assert namespace.testing == self.single_expected(expected)

    def test_parse_multi_args(self):
        self.parser.add_argument('--testing', action=self.action)
        for raw_val, expected in self.test_values:
            namespace = self.parser.parse_args([
                '--testing=' + raw_val, '--testing=' + raw_val,
            ])
            assert namespace.testing == self.multi_expected(expected)


class TestCommaSeparatedValuesAppendAction(TestCommaSeparatedValuesAction):

    def setup_method(self, method):
        super().setup_method(method)
        self.action = 'csv_append'
        self.multi_expected = lambda x: x + x


class TestCommaSeparatedNegationsAction(TestCommaSeparatedValuesAction):

    def setup_method(self, method):
        super().setup_method(method)
        self.test_values = (
            ('', ([], [])),
            (',', ([], [])),
            (',,', ([], [])),
            ('a', ([], ['a'])),
            ('-a', (['a'], [])),
            ('a,-b,-c,d', (['b', 'c'], ['a', 'd'])),
        )
        self.bad_args = ('-',)
        self.action = 'csv_negations'

    def test_parse_bad_args(self):
        self.parser.add_argument('--testing', action=self.action)
        for arg in self.bad_args:
            with pytest.raises(argparse.ArgumentTypeError) as excinfo:
                namespace = self.parser.parse_args(['--testing=' + arg])
            assert 'without a token' in str(excinfo.value)


class TestCommaSeparatedNegationsAppendAction(TestCommaSeparatedNegationsAction):

    def setup_method(self, method):
        super().setup_method(method)
        self.action = 'csv_negations_append'
        self.multi_expected = lambda x: tuple(x + y for x, y in zip(x, x))


class TestCommaSeparatedElementsAction(TestCommaSeparatedNegationsAction):

    def setup_method(self, method):
        super().setup_method(method)
        self.test_values = (
            ('', ([], [], [])),
            (',', ([], [], [])),
            (',,', ([], [], [])),
            ('-a', (['a'], [], [])),
            ('a', ([], ['a'], [])),
            ('+a', ([], [], ['a'])),
            ('a,-b,-c,d', (['b', 'c'], ['a', 'd'], [])),
            ('a,-b,+c,-d,+e,f', (['b', 'd'], ['a', 'f'], ['c', 'e'])),
        )
        self.bad_values = ('-', '+')
        self.action = 'csv_elements'


class TestCommaSeparatedElementsAppendAction(TestCommaSeparatedElementsAction):

    def setup_method(self, method):
        super().setup_method(method)
        self.action = 'csv_elements_append'
        self.multi_expected = lambda x: tuple(x + y for x, y in zip(x, x))


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
        self.parser.set_defaults(test='test')
        namespace = self.parser.parse_args([])
        assert namespace.pop('test') == 'test'

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
