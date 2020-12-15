"""Functionality for reading bash like files

Please note that while this functionality can do variable interpolation,
it strictly treats the source as non-executable code.  It cannot parse
subshells, variable additions, etc.

Its primary usage is for reading things like gentoo make.conf's, or
libtool .la files that are bash compatible, but non-executable.
"""

from shlex import shlex

from .demandload import demand_compile_regexp
from .fileutils import readlines
from .log import logger
from .mappings import ProtectedDict

demand_compile_regexp('line_cont_regexp', r'^(.*[^\\]|)\\$')
demand_compile_regexp('inline_comment_regexp', r'^.*\s#.*$')
demand_compile_regexp('var_find', r'\\?(\${\w+}|\$\w+)')
demand_compile_regexp('backslash_find', r'\\.')
demand_compile_regexp('ansi_escape_re', r'(\x9B|\x1B\[)[0-?]*[ -/]*[@-~]')

__all__ = (
    "iter_read_bash", "read_bash", "read_dict", "read_bash_dict",
    "bash_parser", "BashParseError")


def iter_read_bash(bash_source, allow_inline_comments=True,
                   allow_line_cont=False, enum_line=False):
    """Iterate over a file honoring bash commenting rules and line continuations.

    Note that it's considered good behaviour to close filehandles, as
    such, either iterate fully through this, or use read_bash instead.
    Once the file object is no longer referenced the handle will be
    closed, but be proactive instead of relying on the garbage
    collector.

    :param bash_source: either a file to read from
        or a string holding the filename to open.
    :param allow_inline_comments: whether or not to prune characters
        after a # that isn't at the start of a line.
    :param allow_line_cont: whether or not to respect line continuations
    :return: yields lines w/ commenting stripped out
    """
    if isinstance(bash_source, str):
        bash_source = readlines(bash_source, True)
    s = ''
    for lineno, line in enumerate(bash_source):
        if allow_line_cont and s:
            s += line
        else:
            s = line.lstrip()

        if s:
            if s[0] != '#':
                if allow_inline_comments:
                    if (not allow_line_cont or
                            (allow_line_cont and inline_comment_regexp.match(line))):
                        s = s.split("#", 1)[0].rstrip()
                if allow_line_cont and line_cont_regexp.match(line):
                    s = s.rstrip('\\\n')
                    continue
                if enum_line:
                    yield lineno + 1, s.rstrip()
                else:
                    yield s.rstrip()
            s = ''
    if s:
        if enum_line:
            yield lineno + 1, s
        else:
            yield s


def read_bash(*args, **kwargs):
    """Read a file honoring bash commenting rules.

    See :py:func:`iter_read_bash` for parameter details.

    Returns a list of lines w/ comments stripped out.
    """
    return list(iter_read_bash(*args, **kwargs))


def read_bash_dict(bash_source, vars_dict=None, sourcing_command=None):
    """Read bash source, yielding a dict of vars.

    :param bash_source: either a file to read from
        or a string holding the filename to open
    :param vars_dict: initial 'env' for the sourcing.
        Is protected from modification.
    :type vars_dict: dict or None
    :param sourcing_command: controls whether a source command exists.
        If one does and is encountered, then this func is called.
    :type sourcing_command: callable
    :raise BashParseError: thrown if invalid syntax is encountered.
    :return: dict representing the resultant env if bash executed the source.
    """

    # quite possibly I'm missing something here, but the original
    # portage_util getconfig/varexpand seemed like it only went
    # halfway. The shlex posix mode *should* cover everything.

    if vars_dict is not None:
        d, protected = ProtectedDict(vars_dict), True
    else:
        d, protected = {}, False

    close = False
    infile = None
    if isinstance(bash_source, str):
        f = open(bash_source, "r")
        close = True
        infile = bash_source
    else:
        f = bash_source
    s = bash_parser(f, sourcing_command=sourcing_command, env=d, infile=infile)

    try:
        tok = ""
        try:
            while tok is not None:
                key = s.get_token()
                if key == 'export':
                    # discard 'export' token from "export VAR=VALUE" lines
                    key = s.get_token()
                if key is None:
                    break
                elif key.isspace():
                    # we specifically have to check this, since we're
                    # screwing with the whitespace filters below to
                    # detect empty assigns
                    continue
                eq = s.get_token()
                if eq != '=':
                    raise BashParseError(
                        bash_source, s.lineno,
                        "got token %r, was expecting '='" % eq)
                val = s.get_token()
                if val is None:
                    val = ''
                elif val == 'export':
                    val = s.get_token()
                # look ahead to see if we just got an empty assign.
                next_tok = s.get_token()
                if next_tok == '=':
                    # ... we did.
                    # leftmost insertions, thus reversed ordering
                    s.push_token(next_tok)
                    s.push_token(val)
                    val = ''
                else:
                    s.push_token(next_tok)
                d[key] = val
        except ValueError as e:
            raise BashParseError(bash_source, s.lineno, str(e)) from e
    finally:
        if close and f is not None:
            f.close()
    if protected:
        d = d.new
    return d


def read_dict(bash_source, splitter="=", source_isiter=False,
              allow_inline_comments=True, strip=False, filename=None,
              ignore_errors=False):
    """Read key value pairs from a file, ignoring bash-style comments.

    :param splitter: the string to split on.  Can be None to
        default to str.split's default
    :param bash_source: either a file to read from,
        or a string holding the filename to open.
    :param allow_inline_comments: whether or not to prune characters
        after a # that isn't at the start of a line.
    :param ignore_errors: parse errors are logged instead of raised
    :raise: :py:class:`BashParseError` if there are parse errors found.
    """
    d = {}
    if not source_isiter:
        filename = bash_source
        i = iter_read_bash(
            bash_source, allow_inline_comments=allow_inline_comments)
    else:
        if filename is None:
            # XXX what to do?
            filename = '<unknown>'
        i = bash_source
    line_count = 0
    try:
        for k in i:
            line_count += 1
            try:
                k, v = k.split(splitter, 1)
            except ValueError as e:
                if filename == "<unknown>":
                    filename = getattr(bash_source, 'name', bash_source)
                if ignore_errors:
                    logger.error(
                        'bash parse error in %r, line %s', filename, line_count)
                    continue
                else:
                    raise BashParseError(filename, line_count) from e
            if strip:
                k, v = k.strip(), v.strip()
            if len(v) > 2 and v[0] == v[-1] and v[0] in ("'", '"'):
                v = v[1:-1]
            d[k] = v
    finally:
        del i
    return d


def _nuke_backslash(s):
    s = s.group()
    if s == "\\\n":
        return "\n"
    try:
        return chr(ord(s))
    except TypeError:
        return s[1]


class bash_parser(shlex):
    """Fixed up shlex version for bash parsing.

    Corrects corner cases in quote expansion and adds variable interpolation.
    While it's a fair bit slower than stdlib shlex, it parses a more complete
    subset of bash syntax than stdlib shlex.
    """

    def __init__(self, source, sourcing_command=None, env=None, infile=None):
        """
        :param source: file handle to read from
        :param sourcing_command: token to treat as an include command
        :type sourcing_command: either None, or a string; if None, no includes
            are allowed in this parsing
        :param env: initial environment to use for variable interpolation
        :type env: must be a mapping; if None, an empty dict is used
        """
        self.__dict__['state'] = ' '
        shlex.__init__(self, source, posix=True, infile=infile)
        self.wordchars += "@${}/.-+/:~^*"
        self.wordchars = frozenset(self.wordchars)
        if sourcing_command is not None:
            self.source = sourcing_command
        if env is None:
            env = {}
        self.env = env
        self.__pos = 0

    def __setattr__(self, attr, val):
        if attr == "state":
            if (self.state, val) in (
                    ('"', 'a'), ('a', '"'), ('a', ' '), ("'", 'a')):
                strl = len(self.token)
                if self.__pos != strl:
                    self.changed_state.append(
                        (self.state, self.token[self.__pos:]))
                self.__pos = strl
        self.__dict__[attr] = val

    def sourcehook(self, newfile):
        try:
            return shlex.sourcehook(self, newfile)
        except IOError as e:
            raise BashParseError(newfile, 0, str(e)) from e

    def read_token(self):
        self.changed_state = []
        self.__pos = 0
        token = shlex.read_token(self)
        if token is None:
            return token
        if self.state is None:
            # eof reached.
            self.changed_state.append((self.state, token[self.__pos:]))
        else:
            self.changed_state.append((self.state, self.token[self.__pos:]))
        tok = ''
        for s, t in self.changed_state:
            if s in ('"', "a"):
                tok += self.var_expand(t).replace("\\\n", '')
            else:
                tok += t
        return tok

    def var_expand(self, val):
        prev, pos = 0, 0
        l = []
        while match := var_find.search(val, pos):
            pos = match.start()
            if val[pos] == '\\':
                # it's escaped. either it's \\$ or \\${ , either way,
                # skipping two ahead handles it.
                pos += 2
            else:
                var = val[match.start():match.end()].strip("${}")
                if prev != pos:
                    l.append(val[prev:pos])
                if var in self.env:
                    if not isinstance(self.env[var], str):
                        raise ValueError(
                            "env key %r must be a string, not %s: %r" % (
                                var, type(self.env[var]), self.env[var]))
                    l.append(self.env[var])
                else:
                    l.append("")
                prev = pos = match.end()

        # do \\ cleansing, collapsing val down also.
        val = backslash_find.sub(_nuke_backslash, ''.join(l) + val[prev:])
        return val


class BashParseError(Exception):
    """Exception thrown when a handle being parsed isn't valid bash."""

    def __init__(self, filename, line, errmsg=None):
        if errmsg is not None:
            Exception.__init__(
                self, "error parsing '%s' on or before line %i: err %s" %
                (filename, line, errmsg))
        else:
            Exception.__init__(
                self, "error parsing '%s' on or before line %i" %
                (filename, line))
        self.file, self.line, self.errmsg = filename, line, errmsg
