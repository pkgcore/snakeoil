import pytest

from snakeoil.strings import pluralism, doc_dedent


class TestPluralism:

    def test_none(self):
        # default
        assert pluralism([]) == 's'

        # different suffix for nonexistence
        assert pluralism([], none='') == ''

    def test_singular(self):
        # default
        assert pluralism([1]) == ''

        # different suffix for singular existence
        assert pluralism([1], singular='o') == 'o'

    def test_plural(self):
        # default
        assert pluralism([1, 2]) == 's'

        # different suffix for plural existence
        assert pluralism([1, 2], plural='ies') == 'ies'

    def test_int(self):
        assert pluralism(0) == 's'
        assert pluralism(1) == ''
        assert pluralism(2) == 's'


class TestDocDedent:

    def test_empty(self):
        s = ''
        assert s == doc_dedent(s)

    def test_non_string(self):
        with pytest.raises(TypeError):
            doc_dedent(None)

    def test_line(self):
        s = 'line'
        assert s == doc_dedent(s)

    def test_indented_line(self):
        for indent in ('\t', '    '):
            s = f'{indent}line'
            assert 'line' == doc_dedent(s)

    def test_docstring(self):
        s = """Docstring to test.

        foo bar
        """
        assert 'Docstring to test.\n\nfoo bar\n' == doc_dedent(s)

    def test_all_indented(self):
        s = """\
        Docstring to test.

        foo bar
        """
        assert 'Docstring to test.\n\nfoo bar\n' == doc_dedent(s)
