# Copyright: 2006-2009 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""
Compatibility code, preferring cElementTree, falling back as necessary.
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


def escape(string):
    """
    simple escaping of &, <, and >
    """
    return string.replace("&", "&amp;").replace("<", "&lt;").replace(">",
                                                                     "&gt;")
