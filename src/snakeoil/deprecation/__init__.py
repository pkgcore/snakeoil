"""
Deprecation related functionality.

This provides both a compatibility shim over python versions lacking
warnings.deprecated, while also allowing some very basic extra metadata
to be attached to the deprecation, and tracking all deprecations created
by that registry.  This allows tests to do introspection for deprecations
that can now be removed.

To use this, instantiate a registry, and then use it to decorate functions
(exactly like warnings.deprecated in py3.13).  This just keeps a record of
them so that code analysis can be done for things that need to be removed
when future conditions are met.

"""

__all__ = ("Registry", "suppress_deprecations")


from .registry import Registry
from .util import suppress_deprecations
