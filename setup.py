#!/usr/bin/env python3

import os
import sys

from setuptools import setup

sys.path.insert(0, os.path.abspath('src'))
from snakeoil.dist import distutils_extensions as pkgdist
pkgdist_setup, pkgdist_cmds = pkgdist.setup()
OptionalExtension = pkgdist.OptionalExtension

common_includes = [
    'include/snakeoil/heapdef.h',
    'include/snakeoil/common.h',
]

ext_build_options = dict(
    depends=common_includes,
    include_dirs=['include'],
)

extensions = []


build_deps = []
pkgdist.cython_exts(build_deps, extensions, ext_build_options)


setup(**dict(pkgdist_setup,
    description='misc common functionality and useful optimizations',
    url='https://github.com/pkgcore/snakeoil',
    license='BSD',
    author='Tim Harder',
    author_email='radhermit@gmail.com',
    ext_modules=extensions,
    setup_requires=build_deps,
    headers=common_includes,
    cmdclass=dict(
        pkgdist_cmds,
        build_ext=pkgdist.build_ext,
        ),
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        ],
    )
)
