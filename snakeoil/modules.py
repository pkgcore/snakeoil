# Copyright: 2005-2011 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""
dynamic import functionality
"""

__all__ = ("FailedImport", "load_module", "load_attribute", "load_any")

from snakeoil.compatibility import raise_from, IGNORED_EXCEPTIONS
import sys

class FailedImport(ImportError):
    """
    Raised when a requested target cannot be imported
    """
    def __init__(self, trg, e):
        ImportError.__init__(
            self, "Failed importing target '%s': '%s'" % (trg, e))
        self.trg, self.e = trg, e


def load_module(name):
    """load a module

    :param name: python dotted namespace path of the module to import
    :raise: FailedImport if importing fails
    :return: imported module
    """
    if name in sys.modules:
        return sys.modules[name]
    try:
        m = __import__(name)
        # __import__('foo.bar') returns foo, so...
        for bit in name.split('.')[1:]:
            m = getattr(m, bit)
        return m
    except IGNORED_EXCEPTIONS:
        raise
    except Exception, e:
        raise_from(FailedImport(name, e))


def load_attribute(name):
    """load an attribute from a module

    :param name: python dotted namespace path of the attribute to load from a
        module for example, ``snakeoil.modules.load_module`` would return
        :py:func:`load_module`
    :raise: FailedImport if importing fails, or the requested attribute cannot
        be found
    :return: attribute resolved from `name`
    """
    chunks = name.rsplit(".", 1)
    if len(chunks) == 1:
        raise FailedImport(name, "it isn't an attribute, it's a module")
    try:
        m = load_module(chunks[0])
        m = getattr(m, chunks[1])
        return m
    except (AttributeError, ImportError), e:
        raise_from(FailedImport(name, e))


def load_any(name):
    """load an attribute or a module from a namespace

    :param name: python dotted namespace path of the object to load from a
        module for example, ``snakeoil.modules.load_module`` would return
        :py:func:`load_module`, and ``snakeoil.modules`` would return `modules`
    :raise: FailedImport if importing fails, or the requested attribute cannot
        be found
    :return: object resolved from `name`
    """

    try:
        return load_module(name)
    except FailedImport, fi:
        if not isinstance(fi.e, ImportError):
            raise
    return load_attribute(name)
