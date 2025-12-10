"""Version of tarfile modified strictly for snakeoil.data_sources usage.

This is deprecated.  Use the actual python tarfile module, what this fixed is now in upstream.
"""

from snakeoil._internals import deprecated
from snakeoil.python_namespaces import protect_imports

deprecated.module(
    "This is fully deprecated.  Use pkgcore.fs.tar functionality",
    qualname="snakeoil.tar",
    removal_in=(0, 12, 0),
)


# force a fresh module import of tarfile that is ours to monkey patch.
with protect_imports() as (_paths, modules):
    modules.pop("tarfile", None)
    tarfile = __import__("tarfile")


# add in a tweaked ExFileObject that is usable by snakeoil.data_source
class ExFileObject(tarfile.ExFileObject):
    __slots__ = ()
    exceptions = (EnvironmentError,)


tarfile.fileobject = ExFileObject

# finished monkey patching. now to lift things out of our tarfile
# module into this scope so from/import behaves properly.

locals().update((k, getattr(tarfile, k)) for k in tarfile.__all__)
