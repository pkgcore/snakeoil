"""
functionality for snakeoil.klass, stored here for cycle breaking reasons

Deprecating anything in snakeoil.klass tends to trigger a cycle due to the registry
implementation having to reuse parts of snakeoil.klass.
"""

import operator


def alias_method(attr, name=None, doc=None):
    """at runtime, redirect to another method

    This is primarily useful for when compatibility, or a protocol requires
    you to have the same functionality available at multiple spots- for example
    :py:func:`dict.has_key` and :py:func:`dict.__contains__`.

    :param attr: attribute to redirect to
    :param name: ``__name__`` to force for the new method if desired
    :param doc: ``__doc__`` to force for the new method if desired

    >>> from snakeoil.klass import alias_method
    >>> class foon:
    ...   def orig(self):
    ...     return 1
    ...   alias = alias_method("orig")
    >>> obj = foon()
    >>> assert obj.orig() == obj.alias()
    >>> assert obj.alias() == 1
    """
    grab_attr = operator.attrgetter(attr)

    def _asecond_level_call(self, *a, **kw):
        return grab_attr(self)(*a, **kw)

    if doc is None:
        doc = f"Method alias to invoke :py:meth:`{attr}`."

    _asecond_level_call.__doc__ = doc
    if name:
        _asecond_level_call.__name__ = name
    return _asecond_level_call
