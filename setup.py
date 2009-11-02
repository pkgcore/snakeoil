#!/usr/bin/env python

import os
import sys
import errno
import subprocess
import unittest

from distutils import core, ccompiler, log, errors
from distutils.command import build, sdist, build_ext, build_py, build_scripts, install
from stat import ST_MODE

class OptionalExtension(core.Extension):
    pass

if os.name == "nt":
    bzrbin = "bzr.bat"
else:
    bzrbin = "bzr"

class mysdist(sdist.sdist):

    """sdist command specifying the right files and generating ChangeLog."""

    user_options = sdist.sdist.user_options + [
        ('changelog', None, 'create a ChangeLog [default]'),
        ('no-changelog', None, 'do not create the ChangeLog file'),
        ]

    boolean_options = sdist.sdist.boolean_options + ['changelog']

    negative_opt = {'no-changelog': 'changelog'}
    negative_opt.update(sdist.sdist.negative_opt)

    default_format = dict(sdist.sdist.default_format)
    default_format["posix"] = "bztar"

    def initialize_options(self):
        sdist.sdist.initialize_options(self)
        self.changelog = True

    def get_file_list(self):
        """Get a filelist without doing anything involving MANIFEST files."""
        # This is copied from the "Recreate manifest" bit of sdist.
        self.filelist.findall()
        if self.use_defaults:
            self.add_defaults()

        # This bit is roughly equivalent to a MANIFEST.in template file.
        for key, globs in self.distribution.package_data.iteritems():
            for pattern in globs:
                self.filelist.include_pattern(os.path.join(key, pattern))

        self.filelist.append("AUTHORS")
        self.filelist.append("NOTES")
        self.filelist.append("NEWS")
        self.filelist.append("COPYING")

        self.filelist.include_pattern('.c', prefix='src')
        self.filelist.include_pattern('.h', prefix='include/snakeoil')

        for prefix in ['doc', 'dev-notes']:
            self.filelist.include_pattern('.rst', prefix=prefix)
            self.filelist.exclude_pattern(os.path.sep + 'index.rst',
                                          prefix=prefix)
        self.filelist.append('build_docs.py')
        self.filelist.append('build_api_docs.sh')
        self.filelist.include_pattern('*', prefix='examples')
        self.filelist.include_pattern('*', prefix='bin')

        if self.prune:
            self.prune_file_list()

        # This is not optional: remove_duplicates needs sorted input.
        self.filelist.sort()
        self.filelist.remove_duplicates()

    def make_release_tree(self, base_dir, files):
        """Create and populate the directory tree that is put in source tars.

        This copies or hardlinks "normal" source files that should go
        into the release and adds generated files that should not
        exist in a working tree.
        """
        sdist.sdist.make_release_tree(self, base_dir, files)
        if self.changelog:
            log.info("regenning ChangeLog (may take a while)")
            if subprocess.call(
                [bzrbin, 'log', '--verbose'],
                stdout=open(os.path.join(base_dir, 'ChangeLog'), 'w')):
                raise errors.DistutilsExecError('bzr log failed')
        log.info('generating bzr_verinfo')
        if subprocess.call(
            [bzrbin, 'version-info', '--format=python'],
            stdout=open(os.path.join(
                    base_dir, 'snakeoil', 'bzr_verinfo.py'), 'w')):
            raise errors.DistutilsExecError('bzr version-info failed')


class snakeoil_build_py(build_py.build_py):

    def run(self):
        build_py.build_py.run(self)
        bzr_ver = self.get_module_outfile(
            self.build_lib, ('snakeoil',), 'bzr_verinfo')
        if not os.path.exists(bzr_ver):
            log.info('generating bzr_verinfo')
            if subprocess.call(
                [bzrbin, 'version-info', '--format=python'],
                stdout=open(bzr_ver, 'w')):
                # Not fatal, just less useful --version output.
                log.warn('generating bzr_verinfo failed!')
            else:
                self.byte_compile([bzr_ver])

class snakeoil_build_ext(build_ext.build_ext):

    user_options = build_ext.build_ext.user_options + [
        ("build-optional=", "o", "build optional C modules"),
    ]

    boolean_options = build.build.boolean_options + ["build-optional"]

    def initialize_options(self):
        build_ext.build_ext.initialize_options(self)
        self.build_optional = None

    def finalize_options(self):
        build_ext.build_ext.finalize_options(self)
        if self.build_optional is None:
            self.build_optional = True
        if not self.build_optional:
            self.extensions = [ext for ext in self.extensions if not isinstance(ext, OptionalExtension)] or None

class TestLoader(unittest.TestLoader):

    """Test loader that knows how to recurse packages."""

    def loadTestsFromModule(self, module):
        """Recurses if module is actually a package."""
        paths = getattr(module, '__path__', None)
        tests = [unittest.TestLoader.loadTestsFromModule(self, module)]
        if paths is None:
            # Not a package.
            return tests[0]
        for path in paths:
            for child in os.listdir(path):
                if (child != '__init__.py' and child.endswith('.py') and
                    child.startswith('test')):
                    # Child module.
                    childname = '%s.%s' % (module.__name__, child[:-3])
                else:
                    childpath = os.path.join(path, child)
                    if not os.path.isdir(childpath):
                        continue
                    if not os.path.exists(os.path.join(childpath,
                                                       '__init__.py')):
                        continue
                    # Subpackage.
                    childname = '%s.%s' % (module.__name__, child)
                tests.append(self.loadTestsFromName(childname))
        return self.suiteClass(tests)


testLoader = TestLoader()


class test(core.Command):

    """Run our unit tests in a built copy.

    Based on code from setuptools.
    """

    user_options = []

    def initialize_options(self):
        # Options? What options?
        pass

    def finalize_options(self):
        # Options? What options?
        pass

    def run(self):
        build_ext = self.reinitialize_command('build_ext')
        build_ext.inplace = True
        self.run_command('build_ext')
        # Somewhat hackish: this calls sys.exit.
        unittest.main('snakeoil.test', argv=['setup.py', '-v'], testLoader=testLoader)


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
    extra_compile_args=['-Wall'],
    depends=common_includes,
    include_dirs=['include'],
    )

extensions = []
if sys.version_info < (2, 5):
    # Almost unmodified copy from the python 2.5 source.
    extensions.append(OptionalExtension(
            'snakeoil._compatibility', ['src/compatibility.c'], **extra_kwargs))

if sys.version_info < (3,):
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
        'build_ext': snakeoil_build_ext,
        'build_py': snakeoil_build_py,
        'test': test,
        },
    )
