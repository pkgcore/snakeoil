# Copyright: 2011 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD 3 clause

"""
compatibility module to break an import cycle, do not directly use this

Access this functionality from :py:module:`snakeoil.osutils` instead
"""

__all__ = ("mmap_and_close",)

import os
import mmap

def mmap_and_close(fd, *args, **kwargs):
    """
    see :py:obj:`mmap.mmap`; basically this maps, then closes, to ensure the
    fd doesn't bleed out.
    """
    try:
        return mmap.mmap(fd, *args, **kwargs)
    finally:
        try:
            os.close(fd)
        except EnvironmentError:
            pass
