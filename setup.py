#!/usr/bin/env python

import os
import sys
import errno
import subprocess
import unittest

from distutils import core, ccompiler, log, errors
from distutils.command import build, sdist, build_ext, build_py, build_scripts, install

from snakeoil import distutils_extensions as snk_distutils
OptionalExtension = snk_distutils.OptionalExtension

class mysdist(snk_distutils.sdist):

    """sdist command specifying the right files and generating ChangeLog."""

    package_namespace = 'snakeoil'

    def _add_to_file_list(self):
        self.filelist.include_pattern('.h', prefix='include/snakeoil')


class snakeoil_build_py(snk_distutils.build_py):

    package_namespace = 'snakeoil'
    generate_bzr_ver = False

    def _inner_run(self, py3k_rebuilds):
        snk_distutils.build_py._inner_run(self, py3k_rebuilds)

        if sys.version_info[0:2] >= (2,5) and not self.inplace:
            files = os.listdir(os.path.join(self.build_lib, 'snakeoil', 'xml'))
            for x in files:
                if x.startswith("bundled_elementtree.py"):
                    os.unlink(os.path.join(self.build_lib,
                        'snakeoil', 'xml', x))
            if snk_distutils.is_py3k:
                kill_it = os.path.join(self.build_lib, 'snakeoil', 'xml',
                    'bundled_elementtree.py')
                py3k_rebuilds[:] = [x for x in py3k_rebuilds
                    if not x[0] == kill_it]

        # distutils is stupid.  restore +x on caching_2to3
        path = os.path.join(self.build_lib, 'snakeoil', 'caching_2to3.py')
        mode = os.stat(path).st_mode
        # note, we use the int here for python3k compatibility.
        # 365 == 0555, 4095 = 0777
        os.chmod(path, ((mode | 365) & 4095))



class test(snk_distutils.test):

    default_test_namespace = 'snakeoil.test'


packages = [
    root.replace(os.path.sep, '.')
    for root, dirs, files in os.walk('snakeoil')
    if '__init__.py' in files]

common_includes=[
    'include/snakeoil/py24-compatibility.h',
    'include/snakeoil/heapdef.h',
    'include/snakeoil/common.h',
    ]

extra_kwargs = dict(
    depends=common_includes,
    include_dirs=['include'],
    )

extensions = []
if sys.version_info < (2, 5):
    # Almost unmodified copy from the python 2.5 source.
    extensions.append(OptionalExtension(
            'snakeoil._compatibility', ['src/compatibility.c'], **extra_kwargs))

if not snk_distutils.is_py3k:
    extensions.extend([
        OptionalExtension(
            'snakeoil.osutils._posix', ['src/posix.c'], **extra_kwargs),
        OptionalExtension(
            'snakeoil._klass', ['src/klass.c'], **extra_kwargs),
        OptionalExtension(
            'snakeoil._caching', ['src/caching.c'], **extra_kwargs),
        OptionalExtension(
            'snakeoil._lists', ['src/lists.c'], **extra_kwargs),
        OptionalExtension(
            'snakeoil.osutils._readdir', ['src/readdir.c'], **extra_kwargs),
        OptionalExtension(
            'snakeoil._formatters', ['src/formatters.c'], **extra_kwargs),
        ]
    )

from snakeoil.version import __version__ as VERSION

core.setup(
    name='snakeoil',
    version=VERSION,
    description='misc common functionality, and useful optimizations',
    url='http://www.pkgcore.org/',
    packages=packages,
    ext_modules=extensions,
    headers=common_includes,
    cmdclass={
        'sdist': mysdist,
        'build_ext': snk_distutils.build_ext,
        'build_py': snakeoil_build_py,
        'test': test,
        },
    )
