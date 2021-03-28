#!/usr/bin/env python3

import os
import sys

from setuptools import setup

# ignore system-installed snakeoil if it exists
sys.path.insert(0, os.path.abspath('src'))
from snakeoil.dist import distutils_extensions as pkgdist
pkgdist_setup, pkgdist_cmds = pkgdist.setup()


setup(**dict(
    pkgdist_setup,
    description='misc common functionality and useful optimizations',
    url='https://github.com/pkgcore/snakeoil',
    license='BSD',
    author='Tim Harder',
    author_email='radhermit@gmail.com',
    ext_modules=pkgdist.cython_exts(),
    cmdclass=dict(
        pkgdist_cmds,
        build_ext=pkgdist.build_ext,
    ),
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
    ],
))
