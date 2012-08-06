#!/usr/bin/env python

import os
import sys
import errno
import subprocess
import unittest

from distutils import core, ccompiler, log, errors
from distutils.command import build, sdist, build_ext, build_py, build_scripts

from snakeoil import distutils_extensions as snk_distutils
OptionalExtension = snk_distutils.OptionalExtension

class mysdist(snk_distutils.sdist):

    """sdist command specifying the right files and generating ChangeLog."""

    package_namespace = 'snakeoil'
    old_verinfo = False

    def _add_to_file_list(self):
        self.filelist.include_pattern('.h', prefix='include/snakeoil')
        self.filelist.include_pattern('doc/*')


class snakeoil_build_py(snk_distutils.build_py):

    package_namespace = 'snakeoil'
    generate_verinfo = True

    def _inner_run(self, py3k_rebuilds):
        snk_distutils.build_py._inner_run(self, py3k_rebuilds)

        # distutils is stupid.  restore +x on appropriate scripts
        for script_name in ("caching_2to3.py", "pyflakes_extension.py"):
            path = os.path.join(self.build_lib, 'snakeoil', script_name)
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
    'include/snakeoil/heapdef.h',
    'include/snakeoil/common.h',
    ]

extra_kwargs = dict(
    depends=common_includes,
    include_dirs=['include'],
    )

extensions = []

if not snk_distutils.is_py3k:
    extensions.extend([
        OptionalExtension(
            'snakeoil._posix', ['src/posix.c'], **extra_kwargs),
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
        OptionalExtension(
            'snakeoil.chksum._whirlpool_cdo', ['src/whirlpool_cdo.c'], **extra_kwargs),
        ]
    )

from snakeoil.version import __version__ as VERSION
name = 'snakeoil'
url = 'http://snakeoil.googlecode.com'
cmdclass = {
    'sdist': mysdist,
    'build_ext': snk_distutils.build_ext,
    'build_py': snakeoil_build_py,
    'test': test,
}

command_options = {}

BuildDoc = snk_distutils.sphinx_build_docs()
if BuildDoc:
    cmdclass['build_docs'] = BuildDoc
    command_options['build_docs'] = {
        'version': ('setup.py', VERSION),
        'source_dir': ('setup.py', 'doc'),
    }

core.setup(
    name=name,
    version=VERSION,
    description='misc common functionality, and useful optimizations',
    url=url,
    license='BSD',
    author='Brian Harring',
    author_email='ferringb@gmail.com',
    packages=packages,
    ext_modules=extensions,
    headers=common_includes,
    cmdclass=cmdclass,
    command_options=command_options,
    )
