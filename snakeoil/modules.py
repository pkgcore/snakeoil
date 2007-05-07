# Copyright: 2005 Brian Harring <ferringb@gmail.com>
# License: GPL2

"""
dynamic import functionality
"""

import sys

class FailedImport(ImportError):
    def __init__(self, trg, e):
        ImportError.__init__(
            self, "Failed importing target '%s': '%s'" % (trg, e))
        self.trg, self.e = trg, e


def load_module(name):
    """load 'name' module, throwing a FailedImport if __import__ fails"""
    if name in sys.modules:
        return sys.modules[name]
    try:
        m = __import__(name)
        # __import__('foo.bar') returns foo, so...
        for bit in name.split('.')[1:]:
            m = getattr(m, bit)
        return m
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception, e:
        raise FailedImport(name, e)


def load_attribute(name):
    """load a specific attribute, rather then a module"""
    chunks = name.rsplit(".", 1)
    if len(chunks) == 1:
        raise FailedImport(name, "it isn't an attribute, it's a module")
    try:
        m = load_module(chunks[0])
        m = getattr(m, chunks[1])
        return m
    except (AttributeError, ImportError), e:
        raise FailedImport(name, e)


def load_any(name):
    """Load a module or attribute."""
    try:
        return load_module(name)
    except FailedImport, fi:
        if not isinstance(fi.e, ImportError):
            raise
    return load_attribute(name)
