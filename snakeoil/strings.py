# License: BSD/GPL2

"""string related methods"""


def pluralism(obj, suffixes=('', 's')):
    """Return singular or plural suffix depending on object's length or value."""
    singular, plural = suffixes

    try:
        value = len(obj)
    except TypeError:
        # value is probably an int
        value = obj

    if value > 1:
        return plural
    return singular
