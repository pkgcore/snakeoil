"""Various argparse actions, types, and miscellaneous extensions."""

import argparse
from argparse import (
    ArgumentError, PARSER, REMAINDER, OPTIONAL, ZERO_OR_MORE,
    SUPPRESS, _get_action_name, _SubParsersAction, _, _UNRECOGNIZED_ARGS_ATTR,
)
from collections import Counter
import copy
from functools import partial
import importlib
from itertools import chain
import logging
from operator import attrgetter
import os
import subprocess
import sys
from textwrap import dedent
import traceback

import lazy_object_proxy

from .. import klass
from ..mappings import ImmutableDict
from ..obj import popattr
from ..sequences import split_negations, split_elements
from ..strings import pluralism
from ..version import get_version


# Enable flag to pull extended docs keyword args into arguments during doc
# generation, when disabled the keyword is silently discarded.
_generate_docs = False


@klass.patch('argparse.ArgumentParser.add_subparsers')
@klass.patch('argparse._SubParsersAction.add_parser')
@klass.patch('argparse._ActionsContainer.add_mutually_exclusive_group')
@klass.patch('argparse._ActionsContainer.add_argument_group')
@klass.patch('argparse._ActionsContainer.add_argument')
def _add_argument_docs(orig_func, self, *args, **kwargs):
    """Enable docs keyword argument support for argparse arguments.

    This is used to add extended, rST-formatted docs to man pages (or other
    generated doc formats) without affecting the regular, summarized help
    output for scripts.

    To use, import this module where argparse is used to create parsers so the
    'docs' keyword gets discarded during regular use. For document generation,
    enable the global _generate_docs variable in order to replace the
    summarized help strings with the extended doc strings.
    """
    docs = kwargs.pop('docs', None)
    obj = orig_func(self, *args, **kwargs)
    if _generate_docs and docs is not None:
        if isinstance(docs, (list, tuple)):
            # list args are often used if originator wanted to strip
            # off first description summary line
            docs = '\n'.join(docs)
        docs = '\n'.join(dedent(docs).strip().split('\n'))

        if orig_func.__name__ == 'add_subparsers':
            # store original description before overriding it with extended
            # docs for general subparsers argument groups
            self._subparsers._description = self._subparsers.description
            self._subparsers.description = docs
        elif isinstance(obj, argparse.Action):
            # docs override help for regular arguments
            obj.help = docs
        elif isinstance(obj, argparse._ActionsContainer):
            # store original description before overriding it with extended
            # docs for argument groups
            obj._description = obj.description
            obj.description = docs
    return obj


def _ensure_value(namespace, name, value):
    """Force empty namespace attribute to specified value."""
    if getattr(namespace, name, None) is None:
        setattr(namespace, name, value)
    return getattr(namespace, name)


class ExtendAction(argparse._AppendAction):
    """Force multiple values to always be stored in a flat list."""

    def __call__(self, parser, namespace, values, option_string=None):
        items = copy.copy(_ensure_value(namespace, self.dest, []))
        items.extend(values)
        setattr(namespace, self.dest, items)


class ParseNonblockingStdin(argparse.Action):
    """Accept arguments from standard input in a non-blocking fashion."""

    def __init__(self, *args, **kwargs):
        self.filter_func = kwargs.pop('filter_func', lambda x: x.strip())
        super().__init__(*args, **kwargs)

    def _stdin(self):
        """Generator yielding lines from stdin."""
        while True:
            if line := sys.stdin.readline():
                if self.filter_func(line):
                    yield line.rstrip()
            else:
                break

    def __call__(self, parser, namespace, values, option_string=None):
        if values is not None and len(values) == 1 and values[0] == '-':
            if sys.stdin.isatty():
                raise argparse.ArgumentError(self, "'-' is only valid when piping data in")
            values = self._stdin()
        setattr(namespace, self.dest, values)


class ParseStdin(ExtendAction):
    """Accept arguments from standard input in a blocking fashion."""

    def __init__(self, *args, **kwargs):
        self.filter_func = kwargs.pop('filter_func', lambda x: x.strip())
        super().__init__(*args, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        if values is not None and len(values) == 1 and values[0] == '-':
            if sys.stdin.isatty():
                raise argparse.ArgumentError(self, "'-' is only valid when piping data in")
            values = [x.rstrip() for x in sys.stdin.readlines() if self.filter_func(x)]
            # reassign stdin to allow interactivity (currently only works for unix)
            sys.stdin = open('/dev/tty')
        super().__call__(parser, namespace, values, option_string)


class CommaSeparatedValues(argparse._AppendAction):
    """Split comma-separated values into a list."""

    def parse_values(self, values):
        items = []
        if isinstance(values, str):
            items.extend(x for x in values.split(',') if x)
        else:
            for value in values:
                items.extend(x for x in value.split(',') if x)
        return items

    def __call__(self, parser, namespace, values, option_string=None):
        items = self.parse_values(values)
        setattr(namespace, self.dest, items)


class CommaSeparatedValuesAppend(CommaSeparatedValues, ExtendAction):
    """Split comma-separated values and append them to a list.

    Multiple specified options append to instead of override the parsed args list.
    """

    def __call__(self, parser, namespace, values, option_string=None):
        items = self.parse_values(values)
        ExtendAction.__call__(self, parser, namespace, items, option_string)


class CommaSeparatedNegations(argparse._AppendAction):
    """Split comma-separated enabled and disabled values into lists.

    Disabled values are prefixed with "-" while enabled values are entered as
    is.

    For example, from the sequence "-a,b,c,-d" would result in "a" and "d"
    being registered as disabled while "b" and "c" are enabled.
    """

    def parse_values(self, values):
        disabled, enabled = [], []
        if isinstance(values, str):
            values = [values]
        for value in values:
            try:
                neg, pos = split_negations(x for x in value.split(',') if x)
            except ValueError as e:
                raise argparse.ArgumentTypeError(e)
            disabled.extend(neg)
            enabled.extend(pos)

        if colliding := set(disabled).intersection(enabled):
            collisions = ', '.join(map(repr, sorted(colliding)))
            s = pluralism(colliding)
            msg = f'colliding value{s}: {collisions}'
            raise argparse.ArgumentError(self, msg)

        return disabled, enabled

    def __call__(self, parser, namespace, values, option_string=None):
        disabled, enabled = self.parse_values(values)
        setattr(namespace, self.dest, (disabled, enabled))


class CommaSeparatedNegationsAppend(CommaSeparatedNegations):
    """Split comma-separated enabled and disabled values and append to lists.

    Multiple specified options append to instead of override the parsed args list.
    """

    def __call__(self, parser, namespace, values, option_string=None):
        old = copy.copy(_ensure_value(namespace, self.dest, ([], [])))
        new = self.parse_values(values)
        combined = tuple(o + n for o, n in zip(old, new))
        setattr(namespace, self.dest, combined)


class CommaSeparatedElements(argparse._AppendAction):
    """Split comma-separated disabled/neutral/enabled elements into lists.

    Disabled elements are prefixed with "-", enabled elements are prefixed with
    "+", and neutral elements are unprefixed.

    For example, from the sequence "-a,b,c,-d" would result in "a" and "d"
    being registered as disabled while "b" and "c" are enabled.
    """

    def parse_values(self, values):
        disabled, neutral, enabled = [], [], []
        if isinstance(values, str):
            values = [values]
        for value in values:
            try:
                neg, neu, pos = split_elements(x for x in value.split(',') if x)
            except ValueError as e:
                raise argparse.ArgumentTypeError(e)
            disabled.extend(neg)
            neutral.extend(neu)
            enabled.extend(pos)

        elements = [set(x) for x in (disabled, neutral, enabled) if x]
        if len(elements) > 1 and (colliding := set.intersection(*elements)):
            collisions = ', '.join(map(repr, sorted(colliding)))
            s = pluralism(colliding)
            msg = f'colliding value{s}: {collisions}'
            raise argparse.ArgumentError(self, msg)

        return disabled, neutral, enabled

    def __call__(self, parser, namespace, values, option_string=None):
        disabled, neutral, enabled = self.parse_values(values)
        setattr(namespace, self.dest, (disabled, neutral, enabled))


class CommaSeparatedElementsAppend(CommaSeparatedElements):
    """Split comma-separated enabled and disabled values and append to lists.

    Multiple specified options append to instead of override the parsed args list.
    """

    def __call__(self, parser, namespace, values, option_string=None):
        old = copy.copy(_ensure_value(namespace, self.dest, ([], [], [])))
        new = self.parse_values(values)
        combined = tuple(o + n for o, n in zip(old, new))
        setattr(namespace, self.dest, combined)


class ManHelpAction(argparse._HelpAction):
    """Display man pages for long --help option and abbreviated output for -h."""

    def __call__(self, parser, namespace, values, option_string=None):
        if option_string == '--help':
            # Try spawning man page -- assumes one level deep for subcommand
            # specific man pages with commands separated by hyphen. For example
            # running `pinspect profile --help` tries to open pinspect-profile
            # man page, but `pinspect profile masks --help` also tries to open
            # pinspect-profile.
            man_page = '-'.join(parser.prog.split()[:2])
            p = subprocess.Popen(['man', man_page])
            p.communicate()
            if p.returncode == 0:
                parser.exit()

        # Fallback to outputting abbreviated help if man page doesn't exist or
        # it was explicitly requested via -h.
        parser.print_help()
        parser.exit()


class StoreBool(argparse._StoreAction):

    def __init__(self,
                 option_strings,
                 dest,
                 const=None,
                 default=None,
                 required=False,
                 help=None,
                 metavar='BOOLEAN'):
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            const=const,
            default=default,
            type=self.boolean,
            required=required,
            help=help,
            metavar=metavar)

    @staticmethod
    def boolean(value):
        value = value.lower()
        if value in ('y', 'yes', 'true'):
            return True
        elif value in ('n', 'no', 'false'):
            return False
        raise ValueError("value %r must be [y|yes|true|n|no|false]" % (value,))


class EnableDebug(argparse._StoreTrueAction):

    def __call__(self, parser, namespace, values, option_string=None):
        super().__call__(parser, namespace, values, option_string=option_string)
        logging.root.setLevel(logging.DEBUG)


class Verbosity(argparse.Action):

    def __init__(self, option_strings, dest, default=None, required=False, help=None):
        super().__init__(
            option_strings=option_strings, dest=dest, nargs=0,
            default=default, required=required, help=help)

        # map verbose/quiet args to increment/decrement the underlying verbosity value
        self.value_map = {
            '-q': -1,
            '--quiet': -1,
            '-v': 1,
            '--verbose': 1,
        }

    def __call__(self, parser, namespace, values, option_string=None):
        change = self.value_map.get(option_string, 0)
        count = getattr(namespace, self.dest, 0)
        new = count + change
        # enable info level logs when running in a heightened verbosity state
        if new >= 2:
            logging.root.setLevel(logging.INFO)
        setattr(namespace, self.dest, new)


class DelayedValue:

    def __init__(self, invokable, priority=0):
        self.priority = priority
        if not callable(invokable):
            raise TypeError("invokable must be callable")
        self.invokable = invokable

    def __call__(self, namespace, attr):
        self.invokable(namespace, attr)


class DelayedDefault(DelayedValue):

    @classmethod
    def wipe(cls, attrs, priority):
        if isinstance(attrs, str):
            attrs = (attrs,)
        return cls(partial(cls._wipe, attrs), priority)

    @staticmethod
    def _wipe(attrs, namespace, triggering_attr):
        for attr in attrs:
            try:
                delattr(namespace, attr)
            except AttributeError:
                pass
        try:
            delattr(namespace, triggering_attr)
        except AttributeError:
            pass


class DelayedParse(DelayedValue):

    def __call__(self, namespace, attr):
        self.invokable()


class OrderedParse(DelayedValue):

    def __call__(self, namespace, attr):
        self.invokable(namespace)
        delattr(namespace, attr)


class Delayed(argparse.Action):

    def __init__(self, option_strings, dest, target=None, priority=0, **kwds):
        if target is None:
            raise ValueError("target must be non None for Delayed")

        self.priority = int(priority)
        self.target = target(option_strings=option_strings, dest=dest, **kwds.copy())
        super().__init__(
            option_strings=option_strings[:], dest=dest,
            nargs=kwds.get("nargs", None), required=kwds.get("required", None),
            help=kwds.get("help", None), metavar=kwds.get("metavar", None),
            default=kwds.get("default", None))

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, DelayedParse(
            partial(self.target, parser, namespace, values, option_string),
            self.priority))


class Expansion(argparse.Action):

    def __init__(self, option_strings, dest, nargs=None, help=None,
                 required=None, subst=None):
        if subst is None:
            raise TypeError("substitution string must be set")
        # simple aliases with no required arguments shouldn't need to specify nargs
        if nargs is None:
            nargs = 0

        super().__init__(
            option_strings=option_strings,
            dest=dest,
            help=help,
            required=required,
            default=False,
            nargs=nargs)
        self.subst = tuple(subst)

    def __call__(self, parser, namespace, values, option_string=None):
        actions = parser._actions
        action_map = {}
        vals = values
        if isinstance(values, str):
            vals = [vals]
        dvals = {str(idx): val for idx, val in enumerate(vals)}
        dvals['*'] = ' '.join(vals)

        for action in actions:
            action_map.update((option, action) for option in action.option_strings)

        for chunk in self.subst:
            option, args = chunk[0], chunk[1:]
            action = action_map.get(option)
            args = [x % dvals for x in args]
            if not action:
                raise ValueError(
                    "unable to find option %r for %r" %
                    (option, self.option_strings))
            if action.type is not None:
                args = list(map(action.type, args))
            if action.nargs in (1, None):
                args = args[0]
            action(parser, namespace, args, option_string=option_string)
        setattr(namespace, self.dest, True)


class _SubParser(argparse._SubParsersAction):

    def add_parser(self, name, cls=None, **kwds):
        """Subparser that links description/help if one is specified."""
        description = kwds.get("description")
        help_txt = kwds.get("help")
        if description is None:
            if help_txt is not None:
                kwds["description"] = help_txt
        elif help_txt is None:
            kwds["help"] = description.split('\n', 1)[0]

        # support using a custom parser class for the subparser
        orig_class = self._parser_class
        if cls is not None:
            self._parser_class = cls
        parser = super().add_parser(name, **kwds)
        self._parser_class = orig_class

        return parser

    def _lazy_parser(self, module, subcmd):
        """Lazily-import the subcommand parser for a given module."""
        return getattr(importlib.import_module(module), subcmd)

    def add_command(self, subcmd):
        """Register a given subcommand to be imported on demand.

        Note that this assumes a specific module naming and layout scheme for commands.
        """
        prog = self._prog_prefix
        module = f'{prog}.scripts.{prog}_{subcmd}'
        func = partial(self._lazy_parser, module, subcmd)
        self._name_parser_map[subcmd] = lazy_object_proxy.Proxy(func)

    def __call__(self, parser, namespace, values, option_string=None):
        """override stdlib argparse to revert subparser namespace changes

        Reverts the broken upstream change made in issue #9351 which causes
        issue #23058. This can be dropped when the problem is fixed upstream.
        """
        parser_name = values[0]
        arg_strings = values[1:]

        # set the parser name if requested
        if self.dest is not argparse.SUPPRESS:
            setattr(namespace, self.dest, parser_name)

        # select the parser
        try:
            parser = self._name_parser_map[parser_name]
        except KeyError:
            tup = parser_name, ', '.join(self._name_parser_map)
            msg = _('unknown parser %r (choices: %s)') % tup
            raise argparse.ArgumentError(self, msg)

        # parse all the remaining options into the namespace
        # store any unrecognized options on the object, so that the top
        # level parser can decide what to do with them
        namespace, arg_strings = parser.parse_known_args(arg_strings, namespace)
        if arg_strings:
            vars(namespace).setdefault(argparse._UNRECOGNIZED_ARGS_ATTR, [])
            getattr(namespace, argparse._UNRECOGNIZED_ARGS_ATTR).extend(arg_strings)


class CsvHelpFormatter(argparse.HelpFormatter):
    """Add custom help formatting for comma-separated value actions."""

    def _format_args(self, action, default_metavar):
        get_metavar = self._metavar_formatter(action, default_metavar)
        if isinstance(action, (CommaSeparatedValues, CommaSeparatedValuesAppend)):
            result = '%s[,%s,...]' % get_metavar(2)
        elif isinstance(action, (CommaSeparatedNegations, CommaSeparatedNegationsAppend)):
            result = '%s[,-%s,...]' % get_metavar(2)
        elif isinstance(action, (CommaSeparatedElements, CommaSeparatedElementsAppend)):
            result = '%s[,-%s,+%s...]' % get_metavar(3)
        else:
            result = super()._format_args(action, default_metavar)
        return result


class SortedHelpFormatter(CsvHelpFormatter):
    """Help formatter that sorts arguments by option strings."""

    def add_arguments(self, actions):
        actions = sorted(actions, key=attrgetter('option_strings'))
        super().add_arguments(actions)


class Namespace(argparse.Namespace):
    """Add support for popping attrs from the namespace."""

    def pop(self, key, default=klass.sentinel):
        """Remove and return an object from the namespace if it exists."""
        try:
            return popattr(self, key)
        except AttributeError:
            if default is not klass.sentinel:
                return default
            raise

    def __getattribute__(self, name):
        val = super().__getattribute__(name)
        # collapse any delayed values accessed before arg parsing occurs
        if isinstance(val, DelayedValue):
            val(self, name)
            val = super().__getattribute__(name)
        return val

    def __bool__(self):
        # force empty namespace boolean to be False
        return bool(self.__dict__)


class SubcmdAbbrevArgumentParser(argparse.ArgumentParser):
    """Argparse-compatible argument parser that supports abbreviating subcommands."""

    def _get_values(self, action, arg_strings):
        # for everything but PARSER, REMAINDER args, strip out first '--'
        if action.nargs not in [PARSER, REMAINDER]:
            try:
                arg_strings.remove('--')
            except ValueError:
                pass

        # optional argument produces a default when not present
        if not arg_strings and action.nargs == OPTIONAL:
            if action.option_strings:
                value = action.const
            else:
                value = action.default
            if isinstance(value, str):
                value = self._get_value(action, value)
                self._check_value(action, value)

        # when nargs='*' on a positional, if there were no command-line
        # args, use the default if it is anything other than None
        elif (not arg_strings and action.nargs == ZERO_OR_MORE and
              not action.option_strings):
            if action.default is not None:
                value = action.default
            else:
                value = arg_strings
            self._check_value(action, value)

        # single argument or optional argument produces a single value
        elif len(arg_strings) == 1 and action.nargs in [None, OPTIONAL]:
            arg_string, = arg_strings
            value = self._get_value(action, arg_string)
            self._check_value(action, value)

        # REMAINDER arguments convert all values, checking none
        elif action.nargs == REMAINDER:
            value = [self._get_value(action, v) for v in arg_strings]

        # PARSER arguments convert all values, but check only the first
        elif action.nargs == PARSER:
            value = [self._get_value(action, v) for v in arg_strings]
            # allow subcmd abbreviations for unique matches
            if value[0] not in action.choices:
                cmds = [x for x in action.choices if x.startswith(value[0])]
                if len(cmds) == 1:
                    value[0] = cmds[0]
            self._check_value(action, value[0])

        # SUPPRESS argument does not put anything in the namespace
        elif action.nargs == SUPPRESS:
            value = SUPPRESS

        # all other types of nargs produce a list
        else:
            value = [self._get_value(action, v) for v in arg_strings]
            for v in value:
                self._check_value(action, v)

        # return the converted value
        return value


class OptionalsParser(argparse.ArgumentParser):
    """Argument parser supporting parsing only optional arguments."""

    def parse_known_optionals(self, args=None, namespace=None):
        """Parse known optional arguments until the first positional or -h/--help.

        This is used to allow multiple shortcuts (like -c or -h) at both the
        global command level and the subcommand level. Otherwise, the argparse
        module wouldn't allow two of the same shortcuts to exist at the same
        time.
        """
        if args is None:
            # args default to the system args
            args = sys.argv[1:]
        else:
            # make sure that args are mutable
            args = list(args)

        # default Namespace built from parser defaults
        if namespace is None:
            namespace = Namespace()

        # add any action defaults that aren't present
        for action in self._actions:
            if action.dest is not SUPPRESS:
                if not hasattr(namespace, action.dest):
                    if action.default is not SUPPRESS:
                        setattr(namespace, action.dest, action.default)

        # add any parser defaults that aren't present
        for dest in self._defaults:
            if not hasattr(namespace, dest):
                setattr(namespace, dest, self._defaults[dest])

        # parse the arguments and exit if there are any errors
        try:
            return self._parse_optionals(args, namespace)
        except ArgumentError:
            err = sys.exc_info()[1]
            self.error(str(err))

    def _parse_optionals(self, arg_strings, namespace):
        # replace arg strings that are file references
        if self.fromfile_prefix_chars is not None:
            arg_strings = self._read_args_from_files(arg_strings)

        # map all mutually exclusive arguments to the other arguments
        # they can't occur with
        action_conflicts = {}
        for mutex_group in self._mutually_exclusive_groups:
            group_actions = mutex_group._group_actions
            for i, mutex_action in enumerate(mutex_group._group_actions):
                conflicts = action_conflicts.setdefault(mutex_action, [])
                conflicts.extend(group_actions[:i])
                conflicts.extend(group_actions[i + 1:])

        # find all option indices, and determine the arg_string_pattern
        # which has an 'O' if there is an option at an index,
        # an 'A' if there is an argument, or a '-' if there is a '--'
        option_string_indices = {}
        arg_string_pattern_parts = []
        arg_strings_iter = iter(arg_strings)
        for i, arg_string in enumerate(arg_strings_iter):

            # all args after -- are non-options
            if arg_string == '--':
                arg_string_pattern_parts.append('-')
                for arg_string in arg_strings_iter:
                    arg_string_pattern_parts.append('A')

            # otherwise, add the arg to the arg strings
            # and note the index if it was an option
            else:
                option_tuple = self._parse_optional(arg_string)
                if option_tuple is None:
                    pattern = 'A'
                else:
                    option_string_indices[i] = option_tuple
                    pattern = 'O'
                arg_string_pattern_parts.append(pattern)

        # join the pieces together to form the pattern
        arg_strings_pattern = ''.join(arg_string_pattern_parts)

        # converts arg strings to the appropriate and then takes the action
        seen_actions = set()
        seen_non_default_actions = set()

        def take_action(action, argument_strings, option_string=None):
            seen_actions.add(action)
            argument_values = self._get_values(action, argument_strings)

            # error if this argument is not allowed with other previously
            # seen arguments, assuming that actions that use the default
            # value don't really count as "present"
            if argument_values is not action.default:
                seen_non_default_actions.add(action)
                for conflict_action in action_conflicts.get(action, []):
                    if conflict_action in seen_non_default_actions:
                        msg = _('not allowed with argument %s')
                        action_name = _get_action_name(conflict_action)
                        raise ArgumentError(action, msg % action_name)

            # take the action if we didn't receive a SUPPRESS value
            # (e.g. from a default)
            if argument_values is not SUPPRESS:
                action(self, namespace, argument_values, option_string)

        # function to convert arg_strings into an optional action
        def consume_optional(start_index):

            # get the optional identified at this index
            option_tuple = option_string_indices[start_index]
            action, option_string, explicit_arg = option_tuple

            # identify additional optionals in the same arg string
            # (e.g. -xyz is the same as -x -y -z if no args are required)
            match_argument = self._match_argument
            action_tuples = []
            while True:

                # if we found no optional action, skip it
                if action is None:
                    extras.append(arg_strings[start_index])
                    return start_index + 1

                # if we match help options, skip them for now so subparsers
                # show up in the help output
                if arg_strings[start_index] in ('-h', '--help'):
                    extras.append(arg_strings[start_index])
                    return start_index + 1

                # if there is an explicit argument, try to match the
                # optional's string arguments to only this
                if explicit_arg is not None:
                    arg_count = match_argument(action, 'A')

                    # if the action is a single-dash option and takes no
                    # arguments, try to parse more single-dash options out
                    # of the tail of the option string
                    chars = self.prefix_chars
                    if arg_count == 0 and option_string[1] not in chars:
                        action_tuples.append((action, [], option_string))
                        char = option_string[0]
                        option_string = char + explicit_arg[0]
                        new_explicit_arg = explicit_arg[1:] or None
                        optionals_map = self._option_string_actions
                        if option_string in optionals_map:
                            action = optionals_map[option_string]
                            explicit_arg = new_explicit_arg
                        else:
                            msg = _('ignored explicit argument %r')
                            raise ArgumentError(action, msg % explicit_arg)

                    # if the action expect exactly one argument, we've
                    # successfully matched the option; exit the loop
                    elif arg_count == 1:
                        stop = start_index + 1
                        args = [explicit_arg]
                        action_tuples.append((action, args, option_string))
                        break

                    # error if a double-dash option did not use the
                    # explicit argument
                    else:
                        msg = _('ignored explicit argument %r')
                        raise ArgumentError(action, msg % explicit_arg)

                # if there is no explicit argument, try to match the
                # optional's string arguments with the following strings
                # if successful, exit the loop
                else:
                    start = start_index + 1
                    selected_patterns = arg_strings_pattern[start:]
                    arg_count = match_argument(action, selected_patterns)
                    stop = start + arg_count
                    args = arg_strings[start:stop]
                    action_tuples.append((action, args, option_string))
                    break

            # add the Optional to the list and return the index at which
            # the Optional's string args stopped
            assert action_tuples
            for action, args, option_string in action_tuples:
                take_action(action, args, option_string)
            return stop

        # the list of Positionals left to be parsed; this is modified
        # by consume_positionals()
        positionals = self._get_positional_actions()

        # function to convert arg_strings into positional actions
        def consume_positionals(start_index):
            # match as many Positionals as possible
            match_partial = self._match_arguments_partial
            selected_pattern = arg_strings_pattern[start_index:]
            arg_counts = match_partial(positionals, selected_pattern)

            # slice off the appropriate arg strings for each Positional
            # and add the Positional and its args to the list
            for action, arg_count in zip(positionals, arg_counts):
                args = arg_strings[start_index: start_index + arg_count]
                start_index += arg_count
                take_action(action, args)

            # slice off the Positionals that we just parsed and return the
            # index at which the Positionals' string args stopped
            positionals[:] = positionals[len(arg_counts):]
            return start_index

        # consume Positionals and Optionals alternately, until we have
        # passed the last option string
        extras = []
        start_index = 0
        if option_string_indices:
            max_option_string_index = max(option_string_indices)
        else:
            max_option_string_index = -1
        while start_index <= max_option_string_index:

            # consume any Positionals preceding the next option
            next_option_string_index = min([
                index
                for index in option_string_indices
                if index >= start_index])
            if start_index != next_option_string_index:
                # positionals_end_index = consume_positionals(start_index)
                positionals_end_index = start_index

                # only try to parse the next optional if we didn't consume
                # the option string during the positionals parsing
                if positionals_end_index >= start_index:
                    start_index = positionals_end_index
                    break
                else:
                    start_index = positionals_end_index

            # if we consumed all the positionals we could and we're not
            # at the index of an option string, there were extra arguments
            if start_index not in option_string_indices:
                strings = arg_strings[start_index:next_option_string_index]
                extras.extend(strings)
                start_index = next_option_string_index

            # consume the next optional and any arguments for it
            start_index = consume_optional(start_index)

        # consume any positionals following the last Optional
        # stop_index = consume_positionals(start_index)
        stop_index = start_index

        # if we didn't consume all the argument strings, there were extras
        extras.extend(arg_strings[stop_index:])

        # make sure all required actions were present and also convert
        # action defaults which were not given as arguments
        required_actions = []
        for action in self._actions:
            if action not in seen_actions:
                # ignore required subcommands and positionals as they'll be handled later
                skip = not action.option_strings or isinstance(action, _SubParsersAction)
                if action.required and not skip:
                    required_actions.append(_get_action_name(action))
                else:
                    # Convert action default now instead of doing it before
                    # parsing arguments to avoid calling convert functions
                    # twice (which may fail) if the argument was given, but
                    # only if it was defined already in the namespace
                    if (action.default is not None and
                        isinstance(action.default, str) and
                        hasattr(namespace, action.dest) and
                        action.default is getattr(namespace, action.dest)):
                        setattr(namespace, action.dest,
                                self._get_value(action, action.default))

        if required_actions:
            self.error(_('the following arguments are required: %s') %
                       ', '.join(required_actions))

        # make sure all required groups had one option present
        for group in self._mutually_exclusive_groups:
            if group.required:
                for action in group._group_actions:
                    if action in seen_non_default_actions:
                        break

                # if no actions were used, report the error
                else:
                    names = [_get_action_name(action)
                             for action in group._group_actions
                             if action.help is not SUPPRESS]
                    msg = _('one of the arguments %s is required')
                    self.error(msg % ' '.join(names))

        # return the updated namespace and the extra arguments
        return namespace, extras


class CsvActionsParser(argparse.ArgumentParser):
    """Parser with custom, CSV actions registered for usage."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.register('action', 'csv', CommaSeparatedValues)
        self.register('action', 'csv_append', CommaSeparatedValuesAppend)
        self.register('action', 'csv_negations', CommaSeparatedNegations)
        self.register('action', 'csv_negations_append', CommaSeparatedNegationsAppend)
        self.register('action', 'csv_elements', CommaSeparatedElements)
        self.register('action', 'csv_elements_append', CommaSeparatedElementsAppend)


class CopyableParser(argparse.ArgumentParser):
    """Parser implementing shallow copy() that doesn't allow argument propagation."""

    _attrs = (
        '_registries',
        '_actions',
        '_option_string_actions',
        '_defaults',
        '_has_negative_number_optionals',
        '_mutually_exclusive_groups',
    )

    def copy(self):
        parser = copy.copy(self)
        for attr in self._attrs:
            setattr(parser, attr, getattr(self, attr).copy())

        # create new actions for new parser so new settings don't propagate
        # back to the original actions
        parser._actions = [copy.copy(a) for a in self._actions]

        action_groups = []
        for group in self._action_groups:
            new_group = copy.copy(group)
            # create new actions for new group so new settings don't propagate
            # back to the original group
            new_group._group_actions = [copy.copy(a) for a in group._group_actions]
            for attr in self._attrs:
                setattr(new_group, attr, getattr(parser, attr))
            action_groups.append(new_group)
            if group.title == 'positional arguments':
                parser._positionals = new_group
            elif group.title == 'optional arguments':
                parser._optionals = new_group
            else:
                parser._subparsers = new_group
        parser._action_groups = action_groups

        return parser


class ArgumentParser(OptionalsParser, CsvActionsParser, CopyableParser):
    """Extended, argparse-compatible argument parser."""

    def __init__(self, suppress=False, color=True, debug=True, quiet=True,
                 verbose=True, version=True, add_help=True, sorted_help=False,
                 description=None, docs=None, script=None, prog=None, **kwds):
        self.debug = debug and '--debug' in sys.argv[1:]
        self.verbosity = int(verbose)
        if self.verbosity:
            argv = Counter(sys.argv[1:])
            # Only supports single, short opts (i.e. -vv isn't recognized),
            # post argparsing the proper value supporting those kind of args is
            # in the options namespace.
            self.verbosity = sum(chain.from_iterable((
                (-1 for x in range(argv['-q'] + argv['--quiet'])),
                (1 for x in range(argv['-v'] + argv['--verbose'])),
            )))

        # subparsers action object from calling add_subparsers()
        self.__subparsers = None
        # function to execute for this parser
        self.__main_func = None
        # pre-parse functions to execute for this parser
        self.__pre_parse = []
        # early parse functions to execute for this parser
        self.__early_parse = []
        # defaults setting functions to execute for this parser
        self.__reset_defaults = []

        # Store parent parsers allowing for separating parsing args meant for
        # the root command with args targeted to subcommands. This enables
        # usage such as adding conflicting options to both the root command and
        # subcommands without causing issues in addition to helping support
        # default subparsers.
        self._parents = kwds.get('parents', ())

        # extract the description to use and set docs for doc generation
        description = self._update_desc(description, docs)

        # Consumers can provide the 'script=(__file__, __name__)' parameter in
        # order for version and prog values to be automatically extracted.
        if script is not None:
            try:
                script_path, script_module = script
                if not os.path.exists(script_path):
                    raise TypeError
            except TypeError:
                raise ValueError(
                    "invalid script parameter, should be (__file__, __name__)")

            project = script_module.split('.')[0]
            if prog is None:
                prog = script_module.split('.')[-1]

        if sorted_help:
            formatter = SortedHelpFormatter
        else:
            formatter = CsvHelpFormatter

        super().__init__(
            description=description, formatter_class=formatter,
            prog=prog, add_help=False, **kwds)

        # register our custom actions
        self.register('action', 'parsers', _SubParser)

        if not suppress:
            base_opts = self.add_argument_group('base options')
            if add_help:
                base_opts.add_argument(
                    '-h', '--help', action=ManHelpAction, default=argparse.SUPPRESS,
                    help='show this help message and exit',
                    docs="""
                        Show this help message and exit. To get more
                        information see the related man page.
                    """)
            if version and script is not None:
                # Note that this option will currently only be available on the
                # base command, not on subcommands.
                base_opts.add_argument(
                    '--version', action='version',
                    version=get_version(project, script_path),
                    help="show this program's version info and exit",
                    docs="""
                        Show this program's version information and exit.

                        When running from within a git repo or a version
                        installed from git the latest commit hash and date will
                        be shown.
                    """)
            if debug:
                base_opts.add_argument(
                    '--debug', action=EnableDebug, help='enable debugging checks',
                    docs='Enable debug checks and show verbose debug output.')
            if quiet:
                base_opts.add_argument(
                    '-q', '--quiet', action=Verbosity, dest='verbosity', default=0,
                    help='suppress non-error messages',
                    docs="Suppress non-error, informational messages.")
            if verbose:
                base_opts.add_argument(
                    '-v', '--verbose', action=Verbosity, dest='verbosity', default=0,
                    help='show verbose output',
                    docs="Increase the verbosity of various output.")
            if color:
                base_opts.add_argument(
                    '--color', action=StoreBool,
                    default=sys.stdout.isatty(),
                    help='enable/disable color support',
                    docs="""
                        Toggle colored output support. This can be used to forcibly
                        enable color support when piping output or other sitations
                        where stdout is not a tty.
                    """)

    def _update_desc(self, description=None, docs=None):
        """Extract the description to use.

        Assumes first line is the short description and the remainder should be
        used for generated docs.  Generally this works properly if a module's
        __doc__ attr is assigned to the description parameter.
        """
        description_lines = []
        if description is not None:
            description_lines = description.strip().split('\n', 1)
            description = description_lines[0]
        if _generate_docs:
            if docs is None and len(description_lines) == 2:
                docs = description_lines[1]
            self._docs = docs
        self.description = description
        return description

    @klass.cached_property
    def subparsers(self):
        """Return the set of registered subparsers."""
        parsers = {}
        if self._subparsers is not None:
            for x in self._subparsers._actions:
                if isinstance(x, argparse._SubParsersAction):
                    parsers.update(x._name_parser_map)
        return ImmutableDict(parsers)

    def pre_parse(self, namespace=None):
        # default Namespace built from parser defaults
        if namespace is None:
            namespace = Namespace()

        try:
            # reset any flagged defaults
            for functor, parser in self.__reset_defaults:
                functor(parser, namespace)

            # run registered pre-parse functions
            if self.__pre_parse:
                for functor, parser in self.__pre_parse:
                    functor(parser, namespace)
                # wipe pre-parse functions so they only run once
                del self.__pre_parse[:]
        except ArgumentError:
            err = sys.exc_info()[1]
            self.error(str(err))

        return namespace

    def parse_known_args(self, args, namespace):
        """Add support for running registered pre-parse functions."""
        if args is None:
            # args default to the system args
            args = sys.argv[1:]
        else:
            # make sure that args are mutable
            args = list(args)

        # default Namespace built from parser defaults
        if namespace is None:
            namespace = Namespace()

        # run registered pre-parse functions
        namespace = self.pre_parse(namespace)

        # add any action defaults that aren't present
        for action in self._actions:
            if action.dest is not SUPPRESS:
                if not hasattr(namespace, action.dest):
                    if action.default is not SUPPRESS:
                        setattr(namespace, action.dest, action.default)

        # add any parser defaults that aren't present
        for dest in self._defaults:
            if not hasattr(namespace, dest):
                setattr(namespace, dest, self._defaults[dest])

        try:
            # run registered early parse functions
            if self.__early_parse:
                for functor, parser in self.__early_parse:
                    namespace, args = functor(parser, namespace, args)

            # parse the arguments and exit if there are any errors
            namespace, args = self._parse_known_args(args, namespace)
            if hasattr(namespace, _UNRECOGNIZED_ARGS_ATTR):
                args.extend(getattr(namespace, _UNRECOGNIZED_ARGS_ATTR))
                delattr(namespace, _UNRECOGNIZED_ARGS_ATTR)
            return namespace, args
        except ArgumentError:
            err = sys.exc_info()[1]
            self.error(str(err))

    def parse_args(self, args=None, namespace=None):
        if namespace is None:
            namespace = Namespace()

        args, unknown_args = self.parse_known_args(args, namespace)

        # make sure the correct function and prog are set if running a subcommand
        subcmd_parser = self.subparsers.get(getattr(args, 'subcommand', None), None)
        if subcmd_parser is not None:
            # override the running program with full subcommand
            self.prog = subcmd_parser.prog
            namespace.prog = subcmd_parser.prog
            # override the function to be run if the subcommand sets one
            if subcmd_parser.__main_func is not None:
                namespace.main_func = subcmd_parser.__main_func

        if unknown_args:
            self.error('unrecognized arguments: %s' % ' '.join(unknown_args))

        # Two runs are required; first, handle any suppression defaults
        # introduced. Subparsers defaults cannot override the parent parser, as
        # such a subparser can't turn off config/domain for example. So we
        # first find all DelayedDefault run them, then rescan for delayeds to
        # run. This allows subparsers to introduce a default named for
        # themselves that suppresses the parent.

        # intentionally no protection of suppression code; this should
        # just work.

        i = ((attr, val) for attr, val in args.__dict__.items()
             if isinstance(val, DelayedDefault))
        for attr, functor in sorted(i, key=lambda val: val[1].priority):
            functor(args, attr)

        # now run the delays
        i = ((attr, val) for attr, val in args.__dict__.items()
             if isinstance(val, DelayedValue))
        try:
            for attr, delayed in sorted(i, key=lambda val: val[1].priority):
                delayed(args, attr)
        except (TypeError, ValueError) as e:
            raise TypeError("failed loading/parsing '%s': %s" % (attr, str(e))) from e
        except argparse.ArgumentError:
            e = sys.exc_info()[1]
            self.error(str(e))

        # run final arg validation
        final_checks = [k for k in args.__dict__.keys() if k.startswith('__final_check__')]
        for check in final_checks:
            functor = args.pop(check)
            functor(self, args)

        return args

    def error(self, message, status=2):
        """Print an error message and exit.

        Similar to argparse's error() except usage information is not shown by
        default.
        """
        if self.debug and sys.exc_info() != (None, None, None):
            # output traceback if any exception is on the stack
            traceback.print_exc()
        self.exit(status, '%s: error: %s\n' % (self.prog, message))

    def bind_main_func(self, functor):
        """Decorator to set a main function for the parser."""
        self.set_defaults(main_func=functor)
        self.__main_func = functor
        # override main prog with subcommand prog
        self.set_defaults(prog=self.prog)
        return functor

    def bind_class(self, obj):
        if not isinstance(obj, ArgparseCommand):
            raise ValueError(
                "expected obj to be an instance of "
                "ArgparseCommand; got %r" % (obj,))
        obj.bind_to_parser(self)
        return self

    def bind_reset_defaults(self, functor):
        """Decorator to bind a function for resetting defaults before every parse run."""
        self.__reset_defaults.append((functor, self))
        return functor

    def bind_delayed_default(self, priority, name=None):
        def f(functor, name=name):
            def default(namespace, attr):
                """Only run delayed default functor if the attribute isn't set."""
                if isinstance(object.__getattribute__(namespace, attr), DelayedValue):
                    functor(namespace, attr)
            if name is None:
                name = functor.__name__
            self.set_defaults(**{name: DelayedValue(default, priority)})
            return functor
        return f

    def bind_parse_priority(self, priority):
        def f(functor):
            name = functor.__name__
            self.set_defaults(**{name: OrderedParse(functor, priority)})
            return functor
        return f

    def add_subparsers(self, **kwargs):
        # If add_subparsers() has already been called return the previous
        # object as argparse doesn't allow multiple objects of this type.
        if self.__subparsers is not None:
            return self.__subparsers

        kwargs.setdefault('title', 'subcommands')
        kwargs.setdefault('dest', 'subcommand')
        kwargs.setdefault('prog', self.prog)
        subparsers = argparse.ArgumentParser.add_subparsers(self, **kwargs)
        subparsers.required = True
        self.__subparsers = subparsers
        return subparsers

    def bind_pre_parse(self, functor):
        """Decorator to bind a function for pre-parsing parser manipulation."""
        self.__pre_parse.append((functor, self))
        return functor

    def bind_early_parse(self, functor):
        """Decorator to bind a function for early parsing support."""
        self.__early_parse.append((functor, self))
        return functor

    def bind_final_check(self, functor):
        """Decorator to bind a function for argument validation."""
        name = f'__final_check__{functor.__name__}'
        self.set_defaults(**{name: functor})
        return functor


class ArgparseCommand:

    def bind_to_parser(self, parser):
        parser.bind_main_func(self)

    def __call__(self, namespace, out, err):
        raise NotImplementedError(self, '__call__')


class FileType(argparse.FileType):
    """Extended file object factory supporting binary modes for stdin/stdout.

    See https://bugs.python.org/issue14156 for a discussion of the issue.
    """

    def __call__(self, string):
        # the special argument "-" means sys.std{in,out}
        if string == '-':
            if 'r' in self._mode:
                return sys.stdin.buffer if 'b' in self._mode else sys.stdin
            elif any(c in self._mode for c in 'wax'):
                return sys.stdout.buffer if 'b' in self._mode else sys.stdout
            else:
                msg = _('argument "-" with mode %r') % self._mode
                raise ValueError(msg)

        # all other arguments are used as file names
        try:
            return open(string, self._mode, self._bufsize, self._encoding, self._errors)
        except OSError as e:
            message = _("can't open '%s': %s")
            raise argparse.ArgumentTypeError(message % (string, e))


def existent_path(value):
    """Check if file argument path exists."""
    if not os.path.exists(value):
        raise argparse.ArgumentTypeError(f'nonexistent path: {value!r}')
    try:
        return os.path.realpath(value)
    except EnvironmentError as e:
        raise ValueError(f'while resolving path {value!r}, encountered error: {e}') from e


def existent_dir(value):
    """Check if argument path exists and is a directory."""
    if not os.path.exists(value):
        raise argparse.ArgumentTypeError(f'nonexistent dir: {value!r}')
    elif not os.path.isdir(value):
        raise argparse.ArgumentTypeError(f'file already exists: {value!r}')
    try:
        return os.path.realpath(value)
    except EnvironmentError as e:
        raise ValueError(f'while resolving path {value!r}, encountered error: {e}') from e


def create_dir(value):
    """Check if argument path exists and is a directory, if it doesn't exist create it."""
    path = os.path.realpath(value)
    try:
        os.makedirs(path, exist_ok=True)
    except FileExistsError:
        raise argparse.ArgumentTypeError(f'file already exists: {value!r}')
    except IOError as e:
        raise argparse.ArgumentTypeError(f'failed creating dir: {e}')
    return path


def bounded_int(func, desc, x):
    """Check if argument is an integer and matches defined bounds."""
    try:
        n = int(x)
    except ValueError:
        raise argparse.ArgumentTypeError('invalid integer value')
    if not func(n):
        raise argparse.ArgumentTypeError(f'must be {desc}')
    return n


def positive_int(x):
    """Check if argument is a positive integer."""
    return bounded_int(lambda n: n >= 1, '>= 1', x)
