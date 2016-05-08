# Copyright: 2016 Tim Harder <radhermit@gmail.com>
# License: BSD/GPL2

"""Various argparse actions, types, and miscellaneous extensions."""

import argparse
from functools import partial
import os
import sys

from snakeoil import compatibility
from snakeoil.klass import patch
from snakeoil.demandload import demandload

demandload(
    'inspect',
    'logging',
    'textwrap:dedent',
    'snakeoil:osutils',
    'snakeoil.version:get_version',
    'snakeoil.sequences:split_negations',
)


# Enable flag to pull extended docs keyword args into arguments during doc
# generation, when disabled the keyword is silently discarded.
_generate_docs = False


@patch(argparse.ArgumentParser, 'add_subparsers')
@patch(argparse._SubParsersAction, 'add_parser')
@patch(argparse._ActionsContainer, 'add_mutually_exclusive_group')
@patch(argparse._ActionsContainer, 'add_argument_group')
@patch(argparse._ActionsContainer, 'add_argument')
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
            # docs override description for general subparsers argument groups
            self._subparsers.description = docs
        elif isinstance(obj, argparse.Action):
            # docs override help for regular arguments
            obj.help = docs
        elif isinstance(obj, argparse._ActionsContainer):
            # docs override description for argument groups
            obj.description = docs
    return obj


class ArgumentError(Exception):
    """Generic error relating to argument creation or usage."""
    pass


class ExtendCommaDelimited(argparse._AppendAction):
    """Split comma-separated values into a list."""

    def __call__(self, parser, namespace, values, option_string=None):
        items = []
        if isinstance(values, basestring):
            items.extend(filter(None, values.split(',')))
        else:
            for value in values:
                items.extend(filter(None, value.split(',')))
        setattr(namespace, self.dest, items)


class ExtendCommaDelimitedToggle(argparse._AppendAction):
    """Split comma-separated enabled and disabled values into lists.

    Disabled values are prefixed with "-" while enabled values are entered as
    is.

    For example, from the sequence "-a,b,c,-d" would result in "a" and "d"
    being registered as disabled while "b" and "c" are enabled.
    """

    def __call__(self, parser, namespace, values, option_string=None):
        disabled, enabled = [], []
        if isinstance(values, basestring):
            values = [values]
        for value in values:
            neg, pos = split_negations(filter(None, value.split(',')))
            disabled.extend(neg)
            enabled.extend(pos)
        setattr(namespace, self.dest, (disabled, enabled))


class StoreBool(argparse._StoreAction):
    def __init__(self,
                 option_strings,
                 dest,
                 const=None,
                 default=None,
                 required=False,
                 help=None,
                 metavar='BOOLEAN'):
        super(StoreBool, self).__init__(
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
        super(EnableDebug, self).__call__(
            parser, namespace, values, option_string=option_string)
        logging.root.setLevel(logging.DEBUG)


class DelayedValue(object):

    def __init__(self, invokable, priority):
        self.priority = priority
        if not callable(invokable):
            raise TypeError("invokable must be callable")
        self.invokable = invokable

    def __call__(self, namespace, attr):
        self.invokable(namespace, attr)


class DelayedDefault(DelayedValue):

    @classmethod
    def wipe(cls, attrs, priority):
        if isinstance(attrs, basestring):
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

    def __init__(self, invokable, priority):
        DelayedValue.__init__(self, invokable, priority)

    def __call__(self, namespace, attr):
        self.invokable()


class Delayed(argparse.Action):

    def __init__(self, option_strings, dest, target=None, priority=0, **kwds):
        if target is None:
            raise ValueError("target must be non None for Delayed")

        self.priority = int(priority)
        self.target = target(option_strings=option_strings, dest=dest, **kwds.copy())
        super(Delayed, self).__init__(
            option_strings=option_strings[:],
            dest=dest, nargs=kwds.get("nargs", None), required=kwds.get("required", None),
            help=kwds.get("help", None), metavar=kwds.get("metavar", None))

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

        super(Expansion, self).__init__(
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
        if isinstance(values, basestring):
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
                args = map(action.type, args)
            if action.nargs in (1, None):
                args = args[0]
            action(parser, namespace, args, option_string=option_string)
        setattr(namespace, self.dest, True)


class _SubParser(argparse._SubParsersAction):

    def add_parser(self, name, **kwds):
        """argparser subparser that links description/help if one is specified"""
        description = kwds.get("description")
        help_txt = kwds.get("help")
        if description is None:
            if help_txt is not None:
                kwds["description"] = help_txt
        elif help_txt is None:
            kwds["help"] = description
        return argparse._SubParsersAction.add_parser(self, name, **kwds)

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


class ArgumentParser(argparse.ArgumentParser):

    def __init__(self, suppress=False, color=True, debug=True, quiet=True, verbose=True, version=True,
                 add_help=True, description=None, docs=None, **kwds):
        self.suppress = suppress

        if description is not None:
            description_lines = description.split('\n', 1)
            description = description_lines[0]
            if docs is None and len(description_lines) == 2:
                docs = description_lines[1]
        self.docs = docs

        super(ArgumentParser, self).__init__(
            description=description, add_help=False, **kwds)

        # register our custom actions
        self.register('action', 'parsers', _SubParser)
        self.register('action', 'extend_comma', ExtendCommaDelimited)
        self.register('action', 'extend_comma_toggle', ExtendCommaDelimitedToggle)

        if not self.suppress:
            if add_help:
                self.add_argument(
                    '-h', '--help', action='help', default=argparse.SUPPRESS,
                    help='show this help message and exit',
                    docs="""
                        Show this help message and exit. To get more
                        information see the related man page.
                    """)
            if version:
                # Get the calling script's module and project names. This
                # assumes a script module namespace layout where scripts are
                # located in project.scripts.script_name.
                script = inspect.stack(0)[1][0].f_globals['__file__']
                project = script.split(os.path.sep)[-3]
                self.add_argument(
                    '--version', action='version', version=get_version(project, script),
                    help="show this program's version info and exit",
                    docs="""
                        Show this program's version information and exit.

                        When running from within a git repo or a version
                        installed from git the latest commit hash and date will
                        be shown.
                    """)
            if debug:
                self.add_argument(
                    '--debug', action=EnableDebug, help='enable debugging checks',
                    docs='Enable debug checks and show verbose debug output.')
            if quiet:
                self.add_argument(
                    '-q', '--quiet', action='store_true',
                    help='suppress non-error messages',
                    docs="Suppress non-error, informational messages.")
            if verbose:
                self.add_argument(
                    '-v', '--verbose', action='count',
                    help='show verbose output',
                    docs="Increase the verbosity of various output.")
            if color:
                self.add_argument(
                    '--color', action=StoreBool,
                    default=sys.stdout.isatty(),
                    help='enable/disable color support',
                    docs="""
                        Toggle colored output support. This can be used to forcibly
                        enable color support when piping output or other sitations
                        where stdout is not a tty.
                    """)

    def parse_args(self, args=None, namespace=None):
        args = argparse.ArgumentParser.parse_args(self, args, namespace)

        # two runs are required; first, handle any suppression defaults
        # introduced.  subparsers defaults cannot override the parent parser,
        # as such a subparser can't turn off config/domain for example.
        # so we first find all DelayedDefault
        # run them, then rescan for delayeds to run.
        # this allows subparsers to introduce a default named for themselves
        # that suppresses the parent.

        # intentionally no protection of suppression code; this should
        # just work.

        i = ((attr, val) for attr, val in args.__dict__.iteritems()
             if isinstance(val, DelayedDefault))
        for attr, functor in sorted(i, key=lambda val: val[1].priority):
            functor(args, attr)

        # now run the delays.
        i = ((attr, val) for attr, val in args.__dict__.iteritems()
             if isinstance(val, DelayedValue))
        try:
            for attr, delayed in sorted(i, key=lambda val: val[1].priority):
                delayed(args, attr)
        except (TypeError, ValueError) as err:
            self.error("failed loading/parsing '%s': %s" % (attr, str(err)))
        except (ArgumentError, argparse.ArgumentError):
            err = sys.exc_info()[1]
            self.error(str(err))

        final_check = getattr(args, 'final_check', None)
        if final_check is not None:
            del args.final_check
            final_check(self, args)
        return args

    def error(self, message, status=2):
        """Print an error message and exit.

        Similar to argparse's error() except usage information is not shown by
        default.
        """
        self.exit(status, '%s: error: %s\n' % (self.prog, message))

    def bind_main_func(self, functor):
        self.set_defaults(main_func=functor)
        # override main prog with subcmd prog
        self.set_defaults(prog=self.prog)
        return functor

    def bind_class(self, obj):
        if not isinstance(obj, ArgparseCommand):
            raise ValueError(
                "expected obj to be an instance of "
                "ArgparseCommand; got %r" % (obj,))
        obj.bind_to_parser(self)
        return self

    def bind_delayed_default(self, priority, name=None):
        def f(functor, name=name):
            if name is None:
                name = functor.__name__
            self.set_defaults(**{name: DelayedValue(functor, priority)})
            return functor
        return f

    def add_subparsers(self, **kwargs):
        kwargs.setdefault('title', 'subcommands')
        kwargs.setdefault('dest', 'subcommand')
        subparsers = argparse.ArgumentParser.add_subparsers(self, **kwargs)
        subparsers.required = True
        return subparsers

    def bind_final_check(self, functor):
        self.set_defaults(final_check=functor)
        return functor


class ArgparseCommand(object):

    def bind_to_parser(self, parser):
        parser.bind_main_func(self)

    def __call__(self, namespace, out, err):
        raise NotImplementedError(self, '__call__')


def existent_path(value):
    """Check if file argument path exists."""
    if not os.path.exists(value):
        raise argparse.ArgumentTypeError("nonexistent path: %r" % (value,))
    try:
        return osutils.abspath(value)
    except EnvironmentError as e:
        compatibility.raise_from(
            ValueError(
                "while resolving path %r, encountered error: %r" %
                (value, e)))
