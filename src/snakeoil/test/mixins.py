from snakeoil.deprecation import deprecated

from .._namespaces import PythonNamespaceWalker as _original

PythonNamespaceWalker = deprecated(
    "snakeoil.test.mixins.PythonNamespaceWalker has moved to snakeoil._namespaces.  Preferably remove your dependency on it"
)(_original)  # pyright: ignore[reportAssignmentType]
