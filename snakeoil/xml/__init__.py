# Copyright: 2006-2009 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""
compatibility module with a fallback ElementTree if running python2.4

This is primarily of use only if you're targeting python 2.4; for python2.5
and up, ElementTree is bundled in stdlib as xml.

Generally speaking, if you're not supporting python2.4, import from stdlib
directly instead.

"""
# essentially... prefer cElementTree, then 2.5 bundled, then
# elementtree, then 2.5 bundled, then our own bundled

# "No name etree in module xml", "Reimport cElementTree"
# pylint: disable-msg=E0611,W0404

etree = None
try:
    import cElementTree as etree
except ImportError: pass

if etree is None:
    try:
        from xml.etree import cElementTree as etree
        if not hasattr(etree, 'parse'):
            etree = None
    except ImportError: pass

if etree is None:
    try:
        from elementtree import ElementTree as etree
    except ImportError: pass

if etree is None:
    try:
        from xml.etree import cElementTree as etree
        if not hasattr(etree, 'parse'):
            etree = None
    except ImportError: pass

if etree is None:
    try:
        from xml.etree import ElementTree as etree
    except ImportError: pass

if etree is None:
    try:
        from snakeoil.xml import bundled_elementtree as etree
    except ImportError:
        raise ImportError("no suitable etree module found")


def escape(string):
    """
    simple escaping of &, <, and >
    """
    return string.replace("&", "&amp;").replace("<", "&lt;").replace(">",
                                                                     "&gt;")
