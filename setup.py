#!/usr/bin/env python

import io
import sys

from setuptools import setup, find_packages

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

class config(pkgdist.config):
    if not pkgdist.is_py3k:
        @pkgdist.check_define('HAVE_STAT_TV_NSEC')
        @pkgdist.print_check("Checking for struct stat.st_mtim.tv_nsec")
        def check_HAVE_STAT_TV_NSEC(self):
            return self.check_struct_member('struct stat', 'st_mtim.tv_nsec',
                    ('sys/types.h', 'sys/stat.h'))

        @pkgdist.check_define('HAVE_DIRENT_D_TYPE')
        @pkgdist.print_check("Checking for struct dirent.d_type")
        def check_HAVE_DIRENT_D_TYPE(self):
            return self.check_struct_member('struct dirent', 'd_type',
                    ('dirent.h',))

        @pkgdist.check_define('TIME_T_LONGER_THAN_LONG')
        @pkgdist.print_check("Checking if sizeof(time_t) > sizeof(long)", 'yes', 'no')
        def check_TIME_T_LONGER_THAN_LONG(self):
            # Ye old trick here: the conditional is const, so we can use it
            # as array size. If it evaluates to false, we return -1 which is
            # invalid and causes the compilation to fail.
            return self.try_compile('int x[(sizeof(time_t) > sizeof(long)) ? 1 : -1];',
                    ('sys/types.h',))

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
    version=pkgdist.version(),
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
        'config': config,
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
