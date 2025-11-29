import contextlib
import curses
import os
import pty
from io import BytesIO
from tempfile import TemporaryFile

import pytest

from snakeoil import formatters
from snakeoil.test import protect_process

# protect against python GH #51816 for the curses module.
# Short version: it hard locks the term mode and can't be updated,
# thus we do the nasty in a subprocess.
pythonGHissue51816 = protect_process


class TestPlainTextFormatter:
    kls = staticmethod(formatters.PlainTextFormatter)

    def test_basics(self):
        # As many sporks as fit in 20 chars.
        sporks = " ".join(3 * ("spork",))
        for inputs, output in [
            (("\N{SNOWMAN}",), "?"),
            ((7 * "spork ",), "%s\n%s\n%s" % (sporks, sporks, "spork ")),
            (7 * ("spork ",), "%s \n%s \n%s" % (sporks, sporks, "spork ")),
            ((30 * "a"), 20 * "a" + "\n" + 10 * "a"),
            (30 * ("a",), 20 * "a" + "\n" + 10 * "a"),
        ]:
            stream = BytesIO()
            formatter = self.kls(stream, encoding="ascii")
            formatter.width = 20
            formatter.write(autoline=False, wrap=True, *inputs)
            assert output.encode() == stream.getvalue()

    def test_first_prefix(self):
        # As many sporks as fit in 20 chars.
        for inputs, output in [
            (("\N{SNOWMAN}",), "foon:?"),
            (
                (7 * "spork ",),
                "foon:spork spork\nspork spork spork\nspork spork ",
            ),
            (
                7 * ("spork ",),
                "foon:spork spork \nspork spork spork \nspork spork ",
            ),
            ((30 * "a"), "foon:" + 15 * "a" + "\n" + 15 * "a"),
            (30 * ("a",), "foon:" + 15 * "a" + "\n" + 15 * "a"),
        ]:
            stream = BytesIO()
            formatter = self.kls(stream, encoding="ascii")
            formatter.width = 20
            formatter.write(autoline=False, wrap=True, first_prefix="foon:", *inputs)
            assert output.encode() == stream.getvalue()

    def test_later_prefix(self):
        for inputs, output in [
            (("\N{SNOWMAN}",), "?"),
            (
                (7 * "spork ",),
                "spork spork spork\nfoon:spork spork\nfoon:spork spork ",
            ),
            (
                7 * ("spork ",),
                "spork spork spork \nfoon:spork spork \nfoon:spork spork ",
            ),
            ((30 * "a"), 20 * "a" + "\n" + "foon:" + 10 * "a"),
            (30 * ("a",), 20 * "a" + "\n" + "foon:" + 10 * "a"),
        ]:
            stream = BytesIO()
            formatter = self.kls(stream, encoding="ascii")
            formatter.width = 20
            formatter.later_prefix = ["foon:"]
            formatter.write(wrap=True, autoline=False, *inputs)
            assert output.encode() == stream.getvalue()

    def test_complex(self):
        stream = BytesIO()
        formatter = self.kls(stream, encoding="ascii")
        formatter.width = 9
        formatter.first_prefix = ["foo", None, " d"]
        formatter.later_prefix = ["dorkey"]
        formatter.write("dar bl", wrap=True, autoline=False)
        assert "foo ddar\ndorkeybl".encode() == stream.getvalue()
        formatter.write(" " * formatter.width, wrap=True, autoline=True)
        formatter.stream = stream = BytesIO()
        formatter.write("dar", " b", wrap=True, autoline=False)
        assert "foo ddar\ndorkeyb".encode() == stream.getvalue()
        output = """     rdepends: >=dev-lang/python-2.3 >=sys-apps/sed-4.0.5
                       dev-python/python-fchksum
"""
        stream = BytesIO()
        formatter = self.kls(stream, encoding="ascii", width=80)
        formatter.wrap = True
        assert formatter.autoline
        assert formatter.width == 80
        formatter.later_prefix = ["                       "]
        formatter.write(
            "     rdepends: >=dev-lang/python-2.3 "
            ">=sys-apps/sed-4.0.5 dev-python/python-fchksum"
        )
        assert len(formatter.first_prefix) == 0
        assert len(formatter.later_prefix) == 1
        assert output.encode() == stream.getvalue()
        formatter.write()
        formatter.stream = stream = BytesIO()
        # push it right up to the limit.
        formatter.width = 82
        formatter.write(
            "     rdepends: >=dev-lang/python-2.3 "
            ">=sys-apps/sed-4.0.5 dev-python/python-fchksum"
        )
        assert output.encode() == stream.getvalue()

        formatter.first_prefix = []
        formatter.later_prefix = ["                  "]
        formatter.width = 28
        formatter.autoline = False
        formatter.wrap = True
        formatter.stream = stream = BytesIO()
        input = ("     description: ", "The Portage")
        formatter.write(*input)
        output = "".join(input).rsplit(" ", 1)
        output[1] = "                  %s" % output[1]
        assert "\n".join(output).encode() == stream.getvalue()

    def test_wrap_autoline(self):
        for inputs, output in [
            ((3 * ("spork",)), "spork\nspork\nspork\n"),
            (3 * (("spork",),), "spork\nspork\nspork\n"),
            (((3 * "spork",),), "\nfoonsporks\nfoonporksp\nfoonork\n"),
            (
                (
                    ("fo",),
                    (2 * "spork",),
                ),
                "fo\nsporkspork\n",
            ),
            (
                (
                    ("fo",),
                    (3 * "spork",),
                ),
                "fo\n\nfoonsporks\nfoonporksp\nfoonork\n",
            ),
        ]:
            stream = BytesIO()
            formatter = self.kls(stream, encoding="ascii")
            formatter.width = 10
            for input in inputs:
                formatter.write(wrap=True, later_prefix="foon", *input)
            assert output.encode() == stream.getvalue()


class TerminfoFormatterTest:
    def _test_stream(self, stream, formatter, inputs, output):
        stream.seek(0)
        stream.truncate()
        formatter.write(*inputs)
        stream.seek(0)
        result = stream.read()
        output = "".join(output)
        assert output.encode() == result, "given(%r), expected(%r), got(%r)" % (
            inputs,
            output,
            result,
        )

    @pythonGHissue51816()
    def test_terminfo(self):
        esc = "\x1b["
        stream = TemporaryFile()
        f = formatters.TerminfoFormatter(stream, "ansi", True, "ascii")
        f.autoline = False
        for inputs, output in (
            ((f.bold, "bold"), (esc, "1m", "bold", esc, "0;10m")),
            ((f.underline, "underline"), (esc, "4m", "underline", esc, "0;10m")),
            ((f.fg("red"), "red"), (esc, "31m", "red", esc, "39;49m")),
            (
                (
                    f.fg("red"),
                    "red",
                    f.bold,
                    "boldred",
                    f.fg(),
                    "bold",
                    f.reset,
                    "done",
                ),
                (
                    esc,
                    "31m",
                    "red",
                    esc,
                    "1m",
                    "boldred",
                    esc,
                    "39;49m",
                    "bold",
                    esc,
                    "0;10m",
                    "done",
                ),
            ),
            ((42,), ("42",)),
            (("\N{SNOWMAN}",), ("?",)),
        ):
            self._test_stream(stream, f, inputs, output)
        f.autoline = True
        self._test_stream(stream, f, ("lala",), ("lala", "\n"))

    def test_unsupported_term(self):
        stream = TemporaryFile()
        with pytest.raises(formatters.TerminfoUnsupported):
            formatters.TerminfoFormatter(stream, term="dumb")

    @pythonGHissue51816()
    def test_title(self):
        stream = TemporaryFile()
        try:
            f = formatters.TerminfoFormatter(stream, "xterm+sl", True, "ascii")
        except curses.error:
            pytest.skip("xterm+sl not in terminfo db")
        f.title("TITLE")
        stream.seek(0)
        assert b"\x1b]0;TITLE\x07" == stream.read()


@contextlib.contextmanager
def forced_term(term):
    orig_term = os.environ.get("TERM")
    try:
        os.environ["TERM"] = term
        yield
    finally:
        if orig_term is None:
            del os.environ["TERM"]
        else:
            os.environ["TERM"] = orig_term


# XXX ripped from pkgcore's test_commandline
def _get_pty_pair(encoding="ascii"):
    master_fd, slave_fd = pty.openpty()
    master = os.fdopen(master_fd, "rb", 0)
    out = os.fdopen(slave_fd, "wb", 0)
    return master, out


class TestGetFormatter:
    @pythonGHissue51816()
    def test_dumb_terminal(self):
        master, _out = _get_pty_pair()
        with forced_term("dumb"):
            formatter = formatters.get_formatter(master)
            assert isinstance(formatter, formatters.PlainTextFormatter)

    @pythonGHissue51816()
    def test_vt100_terminal(self):
        master, _out = _get_pty_pair()
        with forced_term("vt100"):
            formatter = formatters.get_formatter(master)
            assert isinstance(formatter, formatters.PlainTextFormatter)

    @pythonGHissue51816()
    def test_smart_terminal(self):
        master, _out = _get_pty_pair()
        with forced_term("xterm"):
            formatter = formatters.get_formatter(master)
            assert isinstance(formatter, formatters.TerminfoFormatter)

    @pythonGHissue51816()
    def test_not_a_tty(self):
        with TemporaryFile() as stream:
            with forced_term("xterm"):
                formatter = formatters.get_formatter(stream)
                assert isinstance(formatter, formatters.PlainTextFormatter)

    @pythonGHissue51816()
    def test_no_fd(self):
        stream = BytesIO()
        with forced_term("xterm"):
            formatter = formatters.get_formatter(stream)
            assert isinstance(formatter, formatters.PlainTextFormatter)
