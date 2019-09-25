"""Import modules on demand.

See https://bugs.python.org/issue17621 for background.
"""

import contextlib
import importlib.machinery
from importlib.util import LazyLoader
import os
import sys


# global flag controlling lazy import support
_disabled = False

# modules that have issues when lazily imported
_skip = frozenset([
    '__builtin__',
    '__future__',
    'builtins',
    'grp',
    'pwd',
    'OpenSSL.SSL', # pyopenssl
])


class _LazyLoader(LazyLoader):
    """LazyLoader with extended support for disabling and skipping modules."""

    def exec_module(self, module):
        """Make the module load lazily."""
        if _disabled or module.__name__ in _skip:
            self.loader.exec_module(module)
        else:
            super().exec_module(module)


# custom loaders using our extended LazyLoader
_extensions_loader = _LazyLoader.factory(
    importlib.machinery.ExtensionFileLoader)
_bytecode_loader = _LazyLoader.factory(
    importlib.machinery.SourcelessFileLoader)
_source_loader = _LazyLoader.factory(importlib.machinery.SourceFileLoader)


def _filefinder(path):
    """Return a custom FileFinder using our lazy loaders."""
    return importlib.machinery.FileFinder(
        path,
        (_extensions_loader, importlib.machinery.EXTENSION_SUFFIXES),
        (_source_loader, importlib.machinery.SOURCE_SUFFIXES),
        (_bytecode_loader, importlib.machinery.BYTECODE_SUFFIXES),
    )


def enable():
    """Enable lazy loading for all future module imports."""
    if os.environ.get('SNAKEOIL_DEMANDIMPORT', 'y').lower() not in ('n', 'no' '0', 'false'):
        sys.path_hooks.insert(0, _filefinder)


def is_enabled():
    """Determine if lazy loading is currently enabled."""
    return _filefinder in sys.path_hooks and not _disabled


def disable():
    """Disable lazy loading for all future module imports."""
    try:
        while True:
            sys.path_hooks.remove(_filefinder)
    except ValueError:
        pass


@contextlib.contextmanager
def disabled():
    """Context manager for temporarily disabling lazy imports.

    Example usage:
    >>>   from importlib.util import _LazyModule
    >>>   from snakeoil import demandimport
    >>>   demandimport.enable()
    >>>
    >>>   with demandimport.disabled():
    >>>      from module import submodule
    >>>   assert not isinstance(submodule, _LazyModule)
    """
    global _disabled
    enabled = is_enabled()
    if enabled:
        _disabled = True
    try:
        yield
    finally:
        if enabled:
            _disabled = False


@contextlib.contextmanager
def enabled():
    """Context manager for temporarily enabling lazy imports.

    Useful as a workaround for avoiding circular import issues.

    Example usage:
    >>>   from importlib.util import _LazyModule
    >>>   from snakeoil import demandimport
    >>>
    >>>   with demandimport.enabled():
    >>>      from module import submodule
    >>>   assert isinstance(submodule, _LazyModule)
    >>>   from module2 import submodule2
    >>>   assert not isinstance(submodule2, _LazyModule)
    """
    global _disabled
    enabled = is_enabled()
    if not enabled:
        _disabled = False
        enable()
    try:
        yield
    finally:
        if not enabled:
            _disabled = True
