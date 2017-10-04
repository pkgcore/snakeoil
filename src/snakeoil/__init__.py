# Copyright: 2005-2010 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""
snakeoil library

This library is a bit of a grabbag of the following:

* implementations that make nasty/hard problems simple in usage
* standard lib fixups; a new style UserDict base class for example that
  is designed around iter* overriding, rather than sequence methods as
  UserDict is.
* python version compatibility; snakeoil supports 2.7 and 3.4 through 3.6,
  exposing fallback implementations of desirable functionality in older python
  versions.
* optimized implementations of common patterns
"""

__title__ = 'snakeoil'
__version__ = '0.7.5'
