"""String related methods."""

from .delayed import regexp

_whitespace_regex = regexp(r"^(?P<indent>\s+)")


def pluralism(obj, none=None, singular="", plural="s"):
    """Return singular or plural suffix depending on object's length or value."""
    # default to plural for empty objects, e.g. there are 0 repos
    if none is None:
        none = plural

    try:
        value = len(obj)
    except TypeError:
        # value is probably an int
        value = obj

    if value == 0:
        return none
    elif value == 1:
        return singular
    return plural


def doc_dedent(s):
    """Support dedenting docstrings with initial line having no indentation."""
    indent: str = ""
    try:
        lines = s.split("\n")
    except AttributeError:
        raise TypeError(f"{s!r} is not a string")
    if lines:
        # find first line with an indent if one exists
        for line in lines:
            if mo := _whitespace_regex.match(line):
                indent = mo.group("indent")
                break
    len_i = len(indent)
    return "\n".join(x[len_i:] if x.startswith(indent) else x for x in lines)
