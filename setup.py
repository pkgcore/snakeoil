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
        for key, globs in self.distribution.package_data.items():
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

    user_options = build_py.build_py.user_options + [("inplace", "i", "do any source conversions in place"),
        ("py2to3-tool=", None, "python conversion tool to use; defualts to 2to3")]

    def initialize_options(self):
        build_py.build_py.initialize_options(self)
        self.inplace = False
        self.py2to3_tool = '2to3'

    def finalize_options(self):
        self.inplace = bool(self.inplace)
        if self.inplace:
            self.build_lib = '.'
        build_py.build_py.finalize_options(self)

    def _compute_py3k_rebuilds(self, force=False):
        pjoin = os.path.join
        for base, mod_name, path in self.find_all_modules():
            try:
                new_mtime = os.lstat(path).st_mtime
            except (OSError, IOError):
                # ok... wtf distutils?
                continue
            trg_path = pjoin(self.build_lib, path)
            if force:
                yield trg_path, new_mtime
                continue
            try:
                old_mtime = os.lstat(trg_path).st_mtime
            except (OSError, IOError):
                yield trg_path, new_mtime
                continue
            if old_mtime != new_mtime:
                yield trg_path, new_mtime

    def run(self):
        is_py3k = sys.version_info[0] >= 3
        py3k_rebuilds = []
        if not self.inplace:
            if is_py3k:
                py3k_rebuilds = list(self._compute_py3k_rebuilds(
                    self.force))
            build_py.build_py.run(self)

        bzr_ver = self.get_module_outfile(
            self.build_lib, ('snakeoil',), 'bzr_verinfo')
        # this should check mtime...
        if not os.path.exists(bzr_ver):
            log.info('generating bzr_verinfo')
            if subprocess.call(
                [bzrbin, 'version-info', '--format=python'],
                stdout=open(bzr_ver, 'w')):
                # Not fatal, just less useful --version output.
                log.warn('generating bzr_verinfo failed!')
            else:
                self.byte_compile([bzr_ver])
                py3k_rebuilds.append((bzr_ver, os.lstat(bzr_ver).st_mtime))

        if sys.version_info[0:2] >= (2,5) and not self.inplace:
            files = os.listdir(os.path.join(self.build_lib, 'snakeoil', 'xml'))
            for x in files:
                if x.startswith("bundled_elementtree.py"):
                    os.unlink(os.path.join(self.build_lib,
                        'snakeoil', 'xml', x))
            if is_py3k:
                kill_it = os.path.join(self.build_lib, 'snakeoil', 'xml',
                    'bundled_elementtree.py')
                py3k_rebuilds = [x for x in py3k_rebuilds
                    if not x[0] == kill_it]

        if not is_py3k:
            return

        log.info("stating py3k conversions")

        null_f = open("/dev/null", "w")

        while py3k_rebuilds:
            chunk = py3k_rebuilds[:10]
            py3k_rebuilds = py3k_rebuilds[10:]
            paths = [x[0] for x in chunk]
            for path in paths:
                log.info("doing py3k conversion of %s..." % path)

            ret = subprocess.call([self.py2to3_tool, "-wn"] + paths,
                stderr=null_f, stdout=null_f, shell=False)

            if ret != 0:
                # rerun to get the output for users.
                for path in paths:
                    ret = subprocess.call(["2to3", mod_path], shell=False)
                    if ret != 0:
                        raise errors.DistutilsExecError(
                            "py3k conversion of %s failed w/ exit code %i"
                            % (path, ret))

            for path, mtime in chunk:
                os.utime(path, (-1, mtime))

        log.info("completed py3k conversions")


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


class test(core.Command):

    """Run our unit tests in a built copy.

    Based on code from setuptools.
    """

    user_options = [("inplace", "i", "do building/testing in place"),
        ("skip-rebuilding", "s", "skip rebuilds. primarily for development"),
        ("disable-fork", None, "disable forking of the testloader; primarily for debugging"),
        ("namespaces=", "t", "run only tests matching these namespaces.  "
            "comma delimited"),
        ("pure-python", None, "disable building of extensions"),
        ("force", "f", "force build_py/build_ext as needed"),
        ("py2to3-tool=", None, "tool to use for 2to3 conversion; passed to build_py"),
        ]

    def initialize_options(self):
        self.inplace = False
        self.disable_fork = False
        self.namespaces = ''
        self.pure_python = False
        self.force = False
        self.py2to3_tool = '2to3'

    def finalize_options(self):
        self.inplace = bool(self.inplace)
        self.disable_fork = bool(self.disable_fork)
        self.pure_python = bool(self.pure_python)
        self.force = bool(self.force)
        if self.namespaces:
            self.namespaces = tuple(set(self.namespaces.split(',')))
        else:
            self.namespaces = ()

    def run(self):
        build_ext = self.reinitialize_command('build_ext')
        build_py = self.reinitialize_command('build_py')
        build_py.py2to3_tool = self.py2to3_tool
        build_ext.inplace = build_py.inplace = self.inplace
        build_ext.force = build_py.force = self.force

        if not self.pure_python:
            self.run_command('build_ext')
        if not self.inplace:
            self.run_command('build_py')

        if not self.inplace:
            raw_syspath = sys.path[:]
            cwd = os.getcwd()
            my_syspath = [x for x in sys.path if x != cwd]
            test_path = os.path.abspath(build_py.build_lib)
            my_syspath.insert(0, test_path)
            mods = build_py.find_all_modules()
            mods_to_wipe = set(x[0] for x in mods)
            mods_to_wipe.update('.'.join(x[:2]) for x in mods)

        if self.disable_fork:
            pid = 0
        else:
            sys.stderr.flush()
            sys.stdout.flush()
            pid = os.fork()
        if not pid:
            if not self.inplace:
                os.environ["PYTHONPATH"] = ':'.join(my_syspath)
                sys.path = my_syspath
                for mod in mods_to_wipe:
                    sys.modules.pop(mod, None)

            # thank you for binding freaking sys.stderr into your prototype
            # unittest...
            sys.stderr.flush()
            os.dup2(sys.stdout.fileno(), sys.stderr.fileno())
            args = ['setup.py', '-v']
            if self.namespaces:
                args.extend(self.namespaces)
                default_mod = None
            else:
                default_mod = 'snakeoil.test'
            unittest.main(default_mod, argv=args, testLoader=TestLoader())
            if not self.disable_fork:
                os._exit(1)
        retval = os.waitpid(pid, 0)[1]
        if retval:
            raise errors.DistutilsExecError("tests failed")


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
