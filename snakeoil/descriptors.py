# Copyright: 2006 Marien Zwart <marienz@gentoo.org>
# License: BSD/GPL2


"""Classes implementing the descriptor protocol."""

__all__ = ("classproperty",)


class classproperty(object):

    """Like the builtin :py:func:`property` but takes a single classmethod.

    Essentially, it allows you to use a property on a class itself- not
    just on it's instances.

    Used like this:

    >>> from snakeoil.descriptors import classproperty
    >>> class foo(object):
    ...
    ...   @classproperty
    ...   def test(cls):
    ...     print("invoked")
    ...     return True
    >>> foo.test
    invoked
    True
    >>> foo().test
    invoked
    True
    """

    def __init__(self, getter):
        self.getter = getter

    def __get__(self, instance, owner):
        return self.getter(owner)
