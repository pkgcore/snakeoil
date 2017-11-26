#!/usr/bin/env python

import os
import sys

from setuptools import setup, Extension

import pkgdist
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


class config(pkgdist.config):
    if not pkgdist.is_py3k:
        @pkgdist.check_define('HAVE_STAT_TV_NSEC')
        @pkgdist.print_check("Checking for struct stat.st_mtim.tv_nsec")
        def check_HAVE_STAT_TV_NSEC(self):
            return self.check_struct_member(
                'struct stat', 'st_mtim.tv_nsec', ('sys/types.h', 'sys/stat.h'))

        @pkgdist.check_define('HAVE_DIRENT_D_TYPE')
        @pkgdist.print_check("Checking for struct dirent.d_type")
        def check_HAVE_DIRENT_D_TYPE(self):
            return self.check_struct_member(
                'struct dirent', 'd_type', ('dirent.h',))

        @pkgdist.check_define('TIME_T_LONGER_THAN_LONG')
        @pkgdist.print_check("Checking if sizeof(time_t) > sizeof(long)", 'yes', 'no')
        def check_TIME_T_LONGER_THAN_LONG(self):
            # Ye old trick here: the conditional is const, so we can use it
            # as array size. If it evaluates to false, we return -1 which is
            # invalid and causes the compilation to fail.
            return self.try_compile(
                'int x[(sizeof(time_t) > sizeof(long)) ? 1 : -1];', ('sys/types.h',))


build_deps = []
if pkgdist.is_py3k:
    pkgdist.cython_exts(build_deps, extensions, ext_build_options)
else:
    extensions.extend([
        OptionalExtension(
            'snakeoil._posix',
            [os.path.join(pkgdist.TOPDIR, 'src', 'posix.c')], **ext_build_options),
        OptionalExtension(
            'snakeoil._klass',
            [os.path.join(pkgdist.TOPDIR, 'src', 'klass.c')], **ext_build_options),
        OptionalExtension(
            'snakeoil._caching',
            [os.path.join(pkgdist.TOPDIR, 'src', 'caching.c')], **ext_build_options),
        OptionalExtension(
            'snakeoil._sequences',
            [os.path.join(pkgdist.TOPDIR, 'src', 'sequences.c')], **ext_build_options),
        OptionalExtension(
            'snakeoil.osutils._readdir',
            [os.path.join(pkgdist.TOPDIR, 'src', 'readdir.c')], **ext_build_options),
        OptionalExtension(
            'snakeoil._formatters',
            [os.path.join(pkgdist.TOPDIR, 'src', 'formatters.c')], **ext_build_options),
        OptionalExtension(
            'snakeoil.chksum._whirlpool_cdo',
            [os.path.join(pkgdist.TOPDIR, 'src', 'whirlpool_cdo.c')], **ext_build_options),
    ])


test_requirements = []
if sys.hexversion < 0x03030000:
    test_requirements.append('mock')

setup(
    description='misc common functionality and useful optimizations',
    url='https://github.com/pkgcore/snakeoil',
    license='BSD',
    author='Brian Harring, Tim Harder',
    author_email='python-snakeoil@googlegroups.com',
    ext_modules=extensions,
    setup_requires=build_deps,
    headers=common_includes,
    tests_require=test_requirements,
    cmdclass=dict(
        pkgdist_cmds,
        build_ext=pkgdist.build_ext,
        build_py=pkgdist.build_py2to3,
        config=config,
        test=pkgdist.test,
    ),
    classifiers=(
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ),
    **pkgdist_setup
)
