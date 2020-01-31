#!/usr/bin/env python3

import argparse
import errno
from functools import partial
from importlib import import_module
import os
import re
from string import capwords
import sys

from ..cli import arghparse
from ..osutils import force_symlink
from ..strings import doc_dedent


# enable extended docs keyword arg support
arghparse._generate_docs = True


def _rst_header(char, text, leading=False, capitalize=True):
    s = char * len(text)
    if capitalize:
        text = capwords(text)
    if leading:
        return [s, text, s, '']
    return [text, s, '']


class RawTextFormatter(argparse.RawTextHelpFormatter):
    """Workaround man page generation issues with default rST output formatting."""

    def _format_action(self, action):
        if action.help is not None:
            # Force help docs to be on a separate line from the options. Sphinx man page
            # generation sometimes messes up formatting without this, e.g. for options with
            # explicit choices the first line of the help docs is often on the same line as
            # the argument and choices instead of matching the indentation level of other
            # arguments.
            action.help = '\n' + action.help.strip()
        return super()._format_action(action)


class ManConverter:
    """Convert argparse help docs into rST man pages."""

    positional_re = re.compile("^([^: \t]+)")
    positional_re = partial(positional_re.sub, ':\g<1>:')

    arg_enumeration_re = re.compile("{([^}]+)}")

    def _rewrite_option(self, text):
        def f(match):
            string = match.group(1)
            string = string.replace(',', '|')
            array = [x.strip() for x in string.split('|')]
            # Specifically return '|' w/out spaces; later code is
            # space sensitive. We do the appropriate replacement as
            # the last step.
            return "<%s>" % ('|'.join(array),)
        text = self.arg_enumeration_re.sub(f, text)
        # Now that we've convert {x,y} style options, we need to next
        # convert multi-argument options into a form that is parsable
        # as a two item tuple.
        l = []
        for chunk in text.split(','):
            chunk = chunk.split()
            if len(chunk) > 2:
                chunk[1:] = ["<%s>" % (' '.join(chunk[1:]),)]
            if not chunk[0].startswith('-'):
                chunk[0] = ':%s:' % (chunk[0],)
            l.append(' '.join(chunk))
        # Recompose the options into one text field.
        text = ', '.join(l)
        # Finally, touch up <x|a> into <x | a>
        return text.replace('|', ' | ')

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
        except EnvironmentError as e:
            if e.errno != errno.ENOENT:
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

        header_chars = headers if headers else ('=', '-', '~', '#', '*', '^')
        self.header_char = header_chars[len(name.split(' ')) - 1]

    def run(self):
        sys.stdout.write("regenerating rst for %s\n" % (self.name,))
        for filename, data in self.process_parser(self.parser, self.name):
            with open(os.path.join(self.out_path, filename + '.rst'), "w") as f:
                f.write("\n".join(data))

        if self.mtime:
            os.utime(self.out_path, (self.mtime, self.mtime))

    @staticmethod
    def _get_formatter(parser, name):
        return RawTextFormatter(name, width=1000, max_help_position=1000)

    def process_positional(self, parser, name, action_group):
        l = []
        h = self._get_formatter(parser, name)
        h.add_arguments(action_group._group_actions)
        data = h.format_help().strip()
        if data:
            l.extend(_rst_header(self.header_char, action_group.title))
            if action_group.description:
                l.extend(doc_dedent(action_group.description).split("\n"))
            l.extend(self.positional_re(x) for x in data.split("\n"))
            l.append('')
        return l

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
                    self.base_path, '%s %s' % (self.name, subcommand), parser,
                    mtime=self.mtime, replace_cmd=self.replace_cmd).run()

            subcmds = []
            for subcommand in action_group._group_actions[0].choices:
                subcmds.append('.. include:: %s.rst' % (subcommand,))
            subcmds.append('')

        return l, subcmds

    def process_action_groups(self, parser, name):
        l = []
        subcmds = []
        for action_group in parser._action_groups:
            if getattr(action_group, 'marker', '') == 'positional' or \
                    action_group.title == 'positional arguments':
                l.extend(self.process_positional(parser, name, action_group))
                continue
            if any(isinstance(x, argparse._SubParsersAction) for x in action_group._group_actions):
                assert len(action_group._group_actions) == 1
                lines, subcmds = self.process_subcommands(parser, name, action_group)
                l.extend(lines)
                continue
            h = self._get_formatter(parser, name)
            h.add_arguments(action_group._group_actions)
            data = h.format_help()
            if not data:
                continue
            l.extend(_rst_header(self.header_char, action_group.title))
            if action_group.description:
                l.extend(doc_dedent(action_group.description).split("\n"))
                l.append('')
            options = data.split('\n')
            for i, opt in enumerate(options):
                l.append(opt)
                if i < len(options)-1 and re.match('\S+', options[i+1]) is not None:
                    # add empty line between options to avoid formatting issues
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
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        # strip the main command from the outputted name
        if self.replace_cmd is not None:
            name = ' '.join([self.replace_cmd] + cmd_parts[1:])

        rst_path = path + '.rst'
        rst_filename = os.path.basename(rst_path)

        # get the short description for the header
        desc = getattr(parser, '_description', parser.description)
        desc = ' - ' + desc if desc else ''
        rst = _rst_header(self.header_char, '%s%s' % (name, desc),
                          leading=main_command, capitalize=False)

        cmd = cmd_parts[-1]
        for filename in ('synopsis', 'description', 'options', 'subcommands'):
            rst.append(".. include:: %s/_%s.rst" % (cmd, filename))
        rst = '\n'.join(rst)

        if main_command:
            # generate missing, generic man page rst docs
            mandir = os.path.abspath(os.path.join(self.base_path, '..', 'man'))
            manpage = os.path.join(mandir, rst_filename)
            if os.path.exists(mandir) and not os.path.isfile(manpage):
                with open(rst_path, 'w') as f:
                    f.write(rst)
                force_symlink(rst_path, manpage)
            force_symlink(rst_path.rsplit('.', 1)[0], manpage.rsplit('.', 1)[0])
        else:
            with open(rst_path, 'w') as f:
                f.write(rst)

        synopsis = _rst_header(self.header_char, "synopsis")
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


if __name__ == '__main__':
    output = sys.argv[1]
    targets = sys.argv[2:]
    if not targets:
        sys.exit(0)
    elif targets[0] == '--conf':
        import conf
        targets = getattr(conf, 'generated_man_pages', [])
    elif len(targets) % 2 != 0:
        print("bad arguments given")
        sys.exit(1)
    else:
        targets = iter(targets)
        targets = zip(targets, targets)
    output = os.path.abspath(output)
    if not os.path.isdir(output):
        os.makedirs(output)
    for source, target in targets:
        ManConverter.regen_if_needed(sys.argv[1], source, target)
