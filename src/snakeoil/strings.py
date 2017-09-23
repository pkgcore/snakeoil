# License: BSD/GPL2

"""string related methods"""


def pluralism(obj, none=None, singular='', plural='s'):
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
