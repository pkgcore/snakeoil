"""
snakeoil library

This library is a bit of a grabbag of the following:

* implementations that make nasty/hard problems simple in usage
* standard lib fixups; a new style UserDict base class for example that
  is designed around iter* overriding, rather than sequence methods as
  UserDict is.
* optimized implementations of common patterns
"""

__title__ = "snakeoil"
# TODO: wire these all against py_build rendered values, or against git.  Don't hardcode it here.
# Once that's done, extend it to the rest of the ecosystem.
__version__ = "0.11.0"
__version_info__ = (0, 11, 0)
__python_mininum_version__ = (3, 11, 0)
