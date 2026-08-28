"""Version of tarfile modified strictly for snakeoil.data_sources usage.

This is deprecated.  Use the actual python tarfile module, what this fixed is now in upstream.
"""

import tarfile

from snakeoil._internals import deprecated

deprecated.module(
    "This is fully deprecated.  Use pkgcore.fs.tar functionality",
    qualname="snakeoil.tar",
    removal_in=(0, 12, 0),
)


class ExFileObject(tarfile.ExFileObject):
    """:py:class:`tarfile.ExFileObject` carrying data_source's `exceptions` attribute.

    This is inert and kept only until this module is removed.  It was meant to be
    what :py:meth:`tarfile.TarFile.extractfile` handed back, but that reads
    ``TarFile.fileobject`` -- a class attribute this was never wired into.
    """

    __slots__ = ()
    exceptions = (EnvironmentError,)


# lift tarfile's exports into this scope so from/import behaves properly.
locals().update((k, getattr(tarfile, k)) for k in tarfile.__all__)
