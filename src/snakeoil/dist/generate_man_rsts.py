import argparse
import errno
import os
import sys
from importlib import import_module
from string import capwords
from unittest.mock import patch

from ..osutils import force_symlink
from ..strings import doc_dedent


def _rst_header(char, text, leading=False, capitalize=True):
    s = char * len(text)
    if capitalize:
        text = capwords(text)
    if leading:
        return [s, text, s, '']
    return [text, s, '']


class RstFormatter(argparse.RawTextHelpFormatter):
    """Render argparse actions as rST option directives for sphinx's std domain."""

    def _format_action(self, action):
        lines = [f'.. option:: {self._format_action_invocation(action)}', '']
        if action.help and (help_text := self._expand_help(action).strip()):
            lines.extend(f'   {x}'.rstrip() for x in help_text.split('\n'))
            lines.append('')
        return "\n".join(lines) + "\n"


class ManConverter:
    """Convert argparse help docs into rST man pages."""

    @classmethod
    def regen_if_needed(cls, base_path, src, out_name=None, force=False):
        if out_name is None:
            out_name = src.rsplit(".", 1)[-1]
        out_path = os.path.join(base_path, out_name)
        script_time = int(os.stat(__file__).st_mtime)
        module = import_module(src)
        cur_time = int(os.stat(module.__file__).st_mtime)
        cur_time = max([cur_time, script_time])
        try:
            trg_time = int(os.stat(out_path).st_mtime)
        except EnvironmentError as exc:
            if exc.errno != errno.ENOENT:
                raise
            trg_time = None

        if trg_time is None or cur_time > trg_time or force:
            cls(base_path, out_name, module.argparser,
                mtime=cur_time, out_name=out_name).run()

    def __init__(self, base_path, name, parser, mtime=None,
                 out_name=None, replace_cmd=None, headers=()):
        self.see_also = []
        self.subcommands_to_generate = []
        self.base_path = base_path
        self.name = name
        if out_name is not None:
            self.out_path = os.path.join(base_path, out_name)
        else:
            self.out_path = os.path.join(self.base_path, *self.name.split(' '))
        self.parser = parser
        self.mtime = mtime
        self.replace_cmd = replace_cmd
        self.mandir = os.path.abspath(os.path.join(self.base_path, '..', 'man'))
        if not os.path.exists(self.mandir):
            os.mkdir(self.mandir)
        elif not os.path.isdir(self.mandir):
            raise Exception(f'man dir {self.mandir} exists, but is not a directory')

        header_chars = headers or ('=', '-', '~', '#', '*', '^')
        self.header_char = header_chars[len(name.split(' ')) - 1]

    def run(self):
        sys.stdout.write(f'regenerating rst for {self.name}\n')
        # enable extended docs keyword arg support
        with patch('snakeoil.cli.arghparse._generate_docs', True):
            for filename, data in self.process_parser(self.parser, self.name):
                with open(os.path.join(self.out_path, f'{filename}.rst'), 'w') as f:
                    f.write('\n'.join(data))

        if self.mtime:
            os.utime(self.out_path, (self.mtime, self.mtime))

    @staticmethod
    def _get_formatter(parser, name):
        return RstFormatter(name, width=1000, max_help_position=1000)

    def process_subcommands(self, parser, name, action_group):
        l = []
        h = self._get_formatter(parser, name)
        h.add_arguments(action_group._group_actions)
        data = h.format_help().strip()
        if data:
            assert len(action_group._group_actions) == 1
            l.extend(_rst_header(self.header_char, action_group.title))
            if action_group.description:
                l.extend(doc_dedent(action_group.description).split("\n"))

            for subcommand, parser in action_group._group_actions[0].choices.items():
                self.__class__(
                    self.base_path, f'{self.name} {subcommand}', parser,
                    mtime=self.mtime, replace_cmd=self.replace_cmd).run()

            subcmds = []
            for subcommand in action_group._group_actions[0].choices:
                subcmds.append(f'.. include:: {subcommand}.rst')
            subcmds.append('')

        return l, subcmds

    def process_action_groups(self, parser, name):
        l = []
        subcmds = []
        for action_group in parser._action_groups:
            if any(isinstance(x, argparse._SubParsersAction) for x in action_group._group_actions):
                assert len(action_group._group_actions) == 1
                lines, subcmds = self.process_subcommands(parser, name, action_group)
                l.extend(lines)
                continue
            h = self._get_formatter(parser, name)
            h.add_arguments(action_group._group_actions)
            data = h.format_help().strip()
            if not data:
                continue
            l.extend(_rst_header(self.header_char, action_group.title))
            if action_group.description:
                l.extend(doc_dedent(action_group.description).split("\n"))
                l.append('')
            l.extend(data.split('\n'))
            l.append('')
        return l, subcmds

    def generate_usage(self, parser, name):
        h = self._get_formatter(parser, name)
        h.add_usage(parser.usage, parser._actions, parser._mutually_exclusive_groups)
        text = h.format_help()
        if text.startswith("usage:"):
            text = text[len("usage:"):].lstrip()
        return (x for x in text.split('\n') if x)

    def process_parser(self, parser, name):
        # forcibly run pre-parse functionality as extra arguments may be added
        parser.pre_parse()

        # subcommands all have names using the format "command subcommand ...",
        # e.g. "pmaint sync" or "pinspect query get_profiles"
        main_command = ' ' not in name

        cmd_parts = name.split(' ')
        cmd_path = os.path.join(*cmd_parts)
        path = os.path.join(self.base_path, cmd_path)
        try:
            os.makedirs(path)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise

        # strip the main command from the outputted name
        if self.replace_cmd is not None:
            name = ' '.join([self.replace_cmd] + cmd_parts[1:])

        rst_path = path + '.rst'
        rst_filename = os.path.basename(rst_path)

        # get the short description for the header
        desc = getattr(parser, '_description', parser.description)
        desc = ' - ' + desc if desc else ''
        rst = _rst_header(self.header_char, f'{name}{desc}',
                          leading=True, capitalize=False)

        cmd = cmd_parts[-1]
        for filename in ('synopsis', 'description', 'options', 'subcommands'):
            rst.append(f'.. include:: {cmd}/_{filename}.rst')
        rst = '\n'.join(rst)

        if main_command:
            # generate missing, generic man page rst docs
            manpage = os.path.join(self.mandir, rst_filename)
            if os.path.exists(self.mandir) and not os.path.isfile(manpage):
                with open(rst_path, 'w') as f:
                    f.write(rst)
                force_symlink(rst_path, manpage)
            force_symlink(rst_path.rsplit('.', 1)[0], manpage.rsplit('.', 1)[0])
        else:
            with open(rst_path, 'w') as f:
                f.write(rst)

        # scope the option directives to this command; synopsis is included first
        synopsis = [f'.. program:: {name}', '']
        synopsis.extend(_rst_header(self.header_char, "synopsis"))
        synopsis.extend(self.generate_usage(parser, name))
        description = []
        docs = getattr(parser, '_docs', None)
        if docs:
            description = _rst_header(self.header_char, "description")
            description.append(doc_dedent(docs).strip())
        options, subcmds = self.process_action_groups(parser, name)

        yield ('_synopsis', synopsis)
        yield ('_description', description)
        yield ('_options', options)
        yield ('_subcommands', subcmds)
