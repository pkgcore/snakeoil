# Copyright: 2011 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD 3 clause

"""
compatibility module to break an import cycle, do not directly use this

Access this functionality from :py:module:`snakeoil.osutils` instead
"""

from snakeoil.demandload import demandload

import os
import mmap


class ClosingMmap(mmap.mmap):

    """
    :py:class:`mmap.mmap` derivate that closes the fd upon .close() invocation
    """

    __slots__ = ("_fd",)

    def __init__(self, fd, length, *args, **kwargs):
        mmap.mmap.__init__(self, fd, length, *args, **kwargs)
        self._fd = fd

    def close(self):
        mmap.mmap.close(self)
        os.close(self._fd)
