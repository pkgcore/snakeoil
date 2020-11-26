import argparse
from functools import partial
from importlib import reload
import os
import tempfile
from unittest import mock

import pytest

from snakeoil.cli import arghparse
from snakeoil.test import argparse_helpers


class TestArgparseDocs:

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


class TestCopyableParser:

    # TODO: move this to a generic argparse fixture
    @pytest.fixture(autouse=True)
    def __setup(self):
        self.parser = argparse_helpers.mangle_parser(arghparse.CopyableParser())

    def test_copy(self):
        new_parser = self.parser.copy()
        assert new_parser is not self.parser

    def test_add_optional_argument(self):
        new_parser = self.parser.copy()

        # only the new parser recognizes the added arg
        new_parser.add_argument('--new', action='store_true')
        args, unknown = new_parser.parse_known_args(['--new'])
        assert args.new
        args, unknown = self.parser.parse_known_args(['--new'])
        assert unknown == ['--new']

        # verify adding args to the old parser don't propagate
        self.parser.add_argument('--old', action='store_true')
        args, unknown = new_parser.parse_known_args(['--old'])
        assert unknown == ['--old']
        args, unknown = self.parser.parse_known_args(['--old'])
        assert args.old

    def test_add_positional_argument(self):
        new_parser = self.parser.copy()

        # only the new parser recognizes the added arg
        new_parser.add_argument('new')
        args, unknown = new_parser.parse_known_args(['x'])
        assert args.new == 'x'
        args, unknown = self.parser.parse_known_args(['x'])
        assert 'new' not in args
        assert unknown == ['x']

        # verify adding args to the old parser don't propagate
        self.parser.add_argument('old', nargs='+')
        args, unknown = new_parser.parse_known_args(['y'])
        assert 'old' not in args
        assert args.new == 'y'
        args, unknown = self.parser.parse_known_args(['y'])
        assert 'new' not in args
        assert args.old == ['y']

    def test_mutually_exclusive_groups(self):
        group = self.parser.add_mutually_exclusive_group()
        new_parser = self.parser.copy()
        new_group = new_parser.add_mutually_exclusive_group()

        group.add_argument('-1')
        group.add_argument('-2')
        new_group.add_argument('-3')
        new_group.add_argument('-4')

        # only the new parser recognizes the added args
        with pytest.raises(argparse_helpers.Error):
            args, unknown = new_parser.parse_known_args(['-3', '-4'])
        # while the original parser does not
        args, unknown = self.parser.parse_known_args(['-3', '-4'])
        assert unknown == ['-3', '-4']

        # only the original parser recognizes the old group args
        with pytest.raises(argparse_helpers.Error):
            args, unknown = self.parser.parse_known_args(['-1', '-2'])
        # while the new parser does not
        args, unknown = new_parser.parse_known_args(['-1', '-2'])
        assert unknown == ['-1', '-2']

    def test_argument_groups(self):
        group = self.parser.add_argument_group('group')
        new_parser = self.parser.copy()
        new_group = new_parser.add_argument_group('new_group')

        group.add_argument('-a')
        new_group.add_argument('-b')

        # only the new parser recognizes the added args
        args, unknown = new_parser.parse_known_args(['-a', '1', '-b', '2'])
        assert args.b == '2'
        assert unknown == ['-a', '1']
        # while the original parser does not
        args, unknown = self.parser.parse_known_args(['-a', '1', '-b', '2'])
        assert args.a == '1'
        assert unknown == ['-b', '2']

    def test_subparsers(self):
        new_parser = self.parser.copy()
        subparsers = self.parser.add_subparsers(description='subparsers')
        new_subparsers = new_parser.add_subparsers(description='new_subparsers')

        cmd = subparsers.add_parser('cmd')
        cmd.add_argument('-a')
        new_cmd = new_subparsers.add_parser('new_cmd')
        new_cmd.add_argument('-b')

        # no args
        args = new_parser.parse_args([])
        assert vars(args) == {}
        args = self.parser.parse_args([])
        assert vars(args) == {}

        # only the respective parsers recognize their subcommands
        with pytest.raises(argparse_helpers.Error) as excinfo:
            args = new_parser.parse_args(['cmd'])
        assert "choose from 'new_cmd'" in str(excinfo.value)
        with pytest.raises(argparse_helpers.Error) as excinfo:
            args = self.parser.parse_args(['new_cmd'])
        assert "choose from 'cmd'" in str(excinfo.value)

        # test subcommand arg parsing
        args, unknown = self.parser.parse_known_args(['cmd', '-a', '1'])
        assert args.a == '1'
        assert unknown == []
        args, unknown = self.parser.parse_known_args(['cmd', '-b', '1'])
        assert unknown == ['-b', '1']

        args, unknown = new_parser.parse_known_args(['new_cmd', '-a', '1'])
        assert unknown == ['-a', '1']
        args, unknown = new_parser.parse_known_args(['new_cmd', '-b', '1'])
        assert args.b == '1'
        assert unknown == []


    def test_defaults(self):
        self.parser.add_argument('--arg', default='abc')
        new_parser = self.parser.copy()

        # verify that new defaults don't propagate back to the original action
        new_parser.set_defaults(arg='def')
        args = self.parser.parse_args([])
        assert args.arg == 'abc'
        args = new_parser.parse_args([])
        assert args.arg == 'def'


class TestOptionalsParser:

    # TODO: move this to a generic argparse fixture
    @pytest.fixture(autouse=True)
    def __setup_optionals_parser(self):
        self.optionals_parser = argparse_helpers.mangle_parser(arghparse.OptionalsParser())

    def test_no_args(self):
        args, unknown = self.optionals_parser.parse_known_optionals([])
        assert vars(args) == {}
        assert unknown == []

    def test_only_positionals(self):
        self.optionals_parser.add_argument('args')
        args, unknown = self.optionals_parser.parse_known_optionals([])
        assert vars(args) == {'args': None}
        assert unknown == []

    def test_optionals(self):
        self.optionals_parser.add_argument('--opt1')
        self.optionals_parser.add_argument('args')
        parse = self.optionals_parser.parse_known_optionals

        # no args
        args, unknown = parse([])
        assert args.opt1 is None
        assert unknown == []

        # only known optional
        args, unknown = parse(['--opt1', 'yes'])
        assert args.opt1 == 'yes'
        assert unknown == []

        # unknown optional
        args, unknown = parse(['--foo'])
        assert args.opt1 is None
        assert unknown == ['--foo']

        # unknown optional and positional
        args, unknown = parse(['--foo', 'arg'])
        assert args.opt1 is None
        assert unknown == ['--foo', 'arg']

        # known optional with unknown optional
        args, unknown = parse(['--opt1', 'yes', '--foo'])
        assert args.opt1 == 'yes'
        assert unknown == ['--foo']
        # different order
        args, unknown = parse(['--foo', '--opt1', 'yes'])
        assert args.opt1 == 'yes'
        assert unknown == ['--foo']

        # known optional with unknown positional
        args, unknown = parse(['--opt1', 'yes', 'arg'])
        assert args.opt1 == 'yes'
        assert unknown == ['arg']
        # known optionals parsing stops at the first positional arg
        args, unknown = parse(['arg', '--opt1', 'yes'])
        assert args.opt1 is None
        assert unknown == ['arg', '--opt1', 'yes']


class TestCsvActionsParser:

    # TODO: move this to a generic argparse fixture
    @pytest.fixture(autouse=True)
    def __setup_csv_actions_parser(self):
        self.csv_parser = argparse_helpers.mangle_parser(arghparse.CsvActionsParser())

    def test_bad_action(self):
        with pytest.raises(ValueError) as excinfo:
            self.csv_parser.add_argument('--arg1', action='unknown')
        assert 'unknown action "unknown"' == str(excinfo.value)

    def test_csv_actions(self):
        self.csv_parser.add_argument('--arg1', action='csv')
        self.csv_parser.add_argument('--arg2', action='csv_append')
        self.csv_parser.add_argument('--arg3', action='csv_negations')
        self.csv_parser.add_argument('--arg4', action='csv_negations_append')
        self.csv_parser.add_argument('--arg5', action='csv_elements')
        self.csv_parser.add_argument('--arg6', action='csv_elements_append')


class TestArgumentParser(TestCsvActionsParser, TestOptionalsParser):

    def test_debug(self):
        # debug passed
        parser = argparse_helpers.mangle_parser(arghparse.ArgumentParser(debug=True))
        namespace = parser.parse_args(["--debug"])
        assert parser.debug is False
        assert namespace.debug is True

        # debug not passed
        namespace = parser.parse_args([])
        assert parser.debug is False
        assert namespace.debug is False

        # debug passed in sys.argv -- early debug attr on the parser instance is set
        with mock.patch('sys.argv', ['script', '--debug']):
            parser = argparse_helpers.mangle_parser(arghparse.ArgumentParser(debug=True))
            assert parser.debug is True

    def test_debug_disabled(self):
        parser = argparse_helpers.mangle_parser(arghparse.ArgumentParser(debug=False))

        # ensure the option isn't there if disabled
        with pytest.raises(argparse_helpers.Error):
            namespace = parser.parse_args(["--debug"])

        namespace = parser.parse_args([])
        # parser attribute still exists
        assert parser.debug is False
        # but namespace attribute doesn't
        assert not hasattr(namespace, 'debug')

    def test_verbosity(self):
        values = (
            ([], 0),
            (['-q'], -1),
            (['--quiet'], -1),
            (['-v'], 1),
            (['--verbose'], 1),
            (['-q', '-v'], 0),
            (['--quiet', '--verbose'], 0),
            (['-q', '-q'], -2),
            (['-v', '-v'], 2),
        )
        for args, val in values:
            with mock.patch('sys.argv', ['script'] + args):
                parser = argparse_helpers.mangle_parser(
                    arghparse.ArgumentParser(quiet=True, verbose=True))
                namespace = parser.parse_args(args)
                assert parser.verbosity == val, '{} failed'.format(args)
                assert namespace.verbosity == val, '{} failed'.format(args)

    def test_verbosity_disabled(self):
        parser = argparse_helpers.mangle_parser(
            arghparse.ArgumentParser(quiet=False, verbose=False))

        # ensure the options aren't there if disabled
        for args in ('-q', '--quiet', '-v', '--verbose'):
            with pytest.raises(argparse_helpers.Error):
                namespace = parser.parse_args([args])

        namespace = parser.parse_args([])
        # parser attribute still exists
        assert parser.verbosity == 0
        # but namespace attribute doesn't
        assert not hasattr(namespace, 'verbosity')


class BaseArgparseOptions:

    def setup_method(self, method):
        self.parser = argparse_helpers.mangle_parser(arghparse.ArgumentParser())


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

    def setup_method(self, method):
        super().setup_method(method)
        self.parser.add_argument(
            "testing", nargs='+', action=arghparse.ParseStdin)

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
                (['\nfoo\n', ' bar ', '\nbaz'], ['\nfoo', ' bar', '\nbaz']),
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
        with mock.patch('os.path.realpath') as realpath:
            realpath.side_effect = OSError(19, 'Random OS error')
            with pytest.raises(argparse_helpers.Error):
                self.parser.parse_args(['--path=%s' % tmpdir])

    def test_regular_usage(self, tmpdir):
        namespace = self.parser.parse_args(['--path=%s' % tmpdir])
        assert namespace.path == str(tmpdir)


class TestExistentDirType(BaseArgparseOptions):

    def setup_method(self, method):
        super().setup_method(method)
        self.parser.add_argument('--path', type=arghparse.existent_dir)

    def test_nonexistent(self):
        # nonexistent path arg raises an error
        with pytest.raises(argparse_helpers.Error):
            self.parser.parse_args(['--path=/path/to/nowhere'])

    def test_os_errors(self, tmp_path):
        # random OS/FS issues raise errors
        with mock.patch('os.path.realpath') as realpath:
            realpath.side_effect = OSError(19, 'Random OS error')
            with pytest.raises(argparse_helpers.Error):
                self.parser.parse_args([f'--path={tmp_path}'])

    def test_file_path(self, tmp_path):
        f = tmp_path / 'file'
        f.touch()
        with pytest.raises(argparse_helpers.Error):
            self.parser.parse_args([f'--path={f}'])

    def test_regular_usage(self, tmp_path):
        namespace = self.parser.parse_args([f'--path={tmp_path}'])
        assert namespace.path == str(tmp_path)


class TestNamespace:

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

    def test_bool(self):
        namespace = arghparse.Namespace()
        assert not namespace
        namespace.arg = 'foo'
        assert namespace


class TestManHelpAction:

    def test_help(self, capsys):
        parser = argparse_helpers.mangle_parser(arghparse.ArgumentParser())
        with mock.patch('subprocess.Popen') as popen:
            # --help long option tries man page first before falling back to help output
            with pytest.raises(argparse_helpers.Exit):
                namespace = parser.parse_args(['--help'])
            popen.assert_called_once()
            assert popen.call_args[0][0][0] == 'man'
            captured = capsys.readouterr()
            assert captured.out.strip().startswith('usage: ')
            popen.reset_mock()

            # -h short option just displays the regular help output
            with pytest.raises(argparse_helpers.Exit):
                namespace = parser.parse_args(['-h'])
            popen.assert_not_called()
            captured = capsys.readouterr()
            assert captured.out.strip().startswith('usage: ')
            popen.reset_mock()
