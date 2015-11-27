#!/usr/bin/env python

import io
import sys

from setuptools import setup, find_packages

from snakeoil import __version__
from snakeoil.dist import distutils_extensions as pkgdist
OptionalExtension = pkgdist.OptionalExtension

common_includes = [
    'include/snakeoil/heapdef.h',
    'include/snakeoil/common.h',
]

extra_kwargs = dict(
    depends=common_includes,
    include_dirs=['include'],
)

extensions = []

if not pkgdist.is_py3k:
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
        ])

test_requirements = []
if sys.hexversion < 0x03030000:
    test_requirements.append('mock')

with io.open('README.rst', encoding='utf-8') as f:
    readme = f.read()

setup(
    name='snakeoil',
    version=__version__,
    description='misc common functionality and useful optimizations',
    long_description=readme,
    url='https://github.com/pkgcore/snakeoil',
    license='BSD',
    author='Brian Harring, Tim Harder',
    author_email='python-snakeoil@googlegroups.com',
    packages=find_packages(),
    ext_modules=extensions,
    headers=common_includes,
    tests_require=test_requirements,
    cmdclass={
        'sdist': pkgdist.sdist,
        'build_ext': pkgdist.build_ext,
        'build_py': pkgdist.build_py,
        'test': pkgdist.test,
    },
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
)
