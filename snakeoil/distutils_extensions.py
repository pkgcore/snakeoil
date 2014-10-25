# Copyright: 2008-2011 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""
collection of distutils extensions adding things like automatic 2to3 translation,
a test runner, basic bzr changelog generation, and working around broken stdlib
extensions CFLAG passing in distutils.

Generally speaking, you should flip through this modules src.
"""

import math
import os
import subprocess
import sys

os.environ["SNAKEOIL_DEMANDLOAD_PROTECTION"] = 'n'
os.environ["SNAKEOIL_DEMANDLOAD_WARN"] = 'n'

from distutils import core, log, errors, cmd
from distutils.command import (
    sdist as dst_sdist, build_ext as dst_build_ext, build_py as dst_build_py,
    build as dst_build)
from distutils.spawn import find_executable

from snakeoil import unittest_extensions


class OptionalExtension(core.Extension):
    """python extension that is optional to build.

    If it's not required to have the exception built, just preferable,
    use this class instead of :py:class:`core.Extension` since the machinery
    in this module relies on isinstance to identify what absolutely must
    be built vs what would be nice to have built.
    """
    pass


if os.name == "nt":
    bzrbin = "bzr.bat"
else:
    bzrbin = "bzr"


class sdist(dst_sdist.sdist):

    """sdist command specifying the right files and generating ChangeLog."""

    default_format = dict(dst_sdist.sdist.default_format)
    default_format["posix"] = "bztar"

    package_namespace = None
    old_verinfo = True

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

        self.filelist.include_pattern('.[ch]', prefix='src')

        self.filelist.exclude_pattern('build')
        self.filelist.exclude_pattern('dist')
        self._add_to_file_list()

        if self.prune:
            self.prune_file_list()

        # This is not optional: remove_duplicates needs sorted input.
        self.filelist.sort()
        self.filelist.remove_duplicates()

    def _add_to_file_list(self):
        pass

    def generate_verinfo(self, base_dir):
        log.info('generating _verinfo')
        from snakeoil.version import get_git_version
        data = get_git_version(base_dir)
        if not data:
            return
        if self.old_verinfo:
            content = 'git rev %s, date %s' % (data['rev'],
                                               data['date'])
            content = 'version_info="%s"' % content
        else:
            content = 'version_info=%r' % (data,)
        path = os.path.join(base_dir, self.package_namespace, '_verinfo.py')
        with open(path, 'w') as f:
            f.write(content)

    def make_release_tree(self, base_dir, files):
        """Create and populate the directory tree that is put in source tars.

        This copies or hardlinks "normal" source files that should go
        into the release and adds generated files that should not
        exist in a working tree.
        """
        dst_sdist.sdist.make_release_tree(self, base_dir, files)
        self.generate_verinfo(base_dir)
        self.cleanup_post_release_tree(base_dir)

    def cleanup_post_release_tree(self, base_dir):
        for base, dirs, files in os.walk(base_dir):
            for x in files:
                if x.endswith(".pyc") or x.endswith(".pyo"):
                    os.unlink(os.path.join(base, x))


class build_py(dst_build_py.build_py):

    user_options = dst_build_py.build_py.user_options + [("inplace", "i", "do any source conversions in place")]

    package_namespace = None
    generate_verinfo = False

    def initialize_options(self):
        dst_build_py.build_py.initialize_options(self)
        self.inplace = False

    def finalize_options(self):
        self.inplace = bool(self.inplace)
        if self.inplace:
            self.build_lib = '.'
        dst_build_py.build_py.finalize_options(self)

    def _compute_py3k_rebuilds(self, force=False):
        for base, mod_name, path in self.find_all_modules():
            try:
                new_mtime = math.floor(os.lstat(path).st_mtime)
            except EnvironmentError:
                # ok... wtf distutils?
                continue
            trg_path = os.path.join(self.build_lib, path)
            if force:
                yield trg_path, new_mtime
                continue
            try:
                old_mtime = math.floor(os.lstat(trg_path).st_mtime)
            except EnvironmentError:
                yield trg_path, new_mtime
                continue
            if old_mtime != new_mtime:
                yield trg_path, new_mtime

    def _inner_run(self, py3k_rebuilds):
        pass

    def _run_generate_verinfo(self, py3k_rebuilds):
        ver_path = self.get_module_outfile(
            self.build_lib, (self.package_namespace,), '_verinfo')
        # this should check mtime...
        if not os.path.exists(ver_path):
            log.info('generating _verinfo')
            from snakeoil import version
            with open(ver_path, 'w') as f:
                f.write("version_info=%r" % (version.get_git_version('.'),))
            self.byte_compile([ver_path])
            py3k_rebuilds.append((ver_path, os.lstat(ver_path).st_mtime))

    def get_py2to3_converter(self, options=None, proc_count=0):
        from lib2to3 import refactor as ref_mod
        from snakeoil import caching_2to3

        if (sys.version_info >= (3,0) and sys.version_info < (3,1,2)) or \
            (sys.version_info >=  (2,6) and sys.version_info < (2,6,5)):
            if proc_count not in (0, 1):
                log.warn("disabling parallelization: you're running a python "
                    "version with a broken multiprocessing.queue.JoinableQueue.put "
                    "(python bug 4660).")
            proc_count = 1
        elif proc_count == 0:
            import multiprocessing
            proc_count = multiprocessing.cpu_count()

        assert proc_count >= 1

        if proc_count > 1 and not caching_2to3.multiprocessing_available:
            proc_count = 1

        refactor_kls = caching_2to3.MultiprocessRefactoringTool

        fixer_names = ref_mod.get_fixers_from_package('lib2to3.fixes')
        f = refactor_kls(fixer_names, options=options).refactor

        def f2(*args, **kwds):
            if caching_2to3.multiprocessing_available:
                kwds['num_processes'] = proc_count
            return f(*args, **kwds)

        return f2

    def run(self):
        py3k_rebuilds = []
        if not self.inplace:
            if is_py3k:
                py3k_rebuilds = list(self._compute_py3k_rebuilds(
                    self.force))
            dst_build_py.build_py.run(self)

        if self.generate_verinfo:
            self._run_generate_verinfo(py3k_rebuilds)

        self._inner_run(py3k_rebuilds)

        if not is_py3k:
            return

        converter = self.get_py2to3_converter()
        log.info("starting 2to3 conversion; this may take a while...")
        converter([x[0] for x in py3k_rebuilds], write=True)
        for path, mtime in py3k_rebuilds:
            os.utime(path, (-1, mtime))

        log.info("completed py3k conversions")


class build_ext(dst_build_ext.build_ext):

    user_options = dst_build_ext.build_ext.user_options + [
        ("build-optional=", "o", "build optional C modules"),
        ("disable-distutils-flag-fixing", None, "disable fixing of issue "
            "969718 in python, adding missing -fno-strict-aliasing"),
    ]

    boolean_options = dst_build.build.boolean_options + ["build-optional"]

    def initialize_options(self):
        dst_build_ext.build_ext.initialize_options(self)
        self.build_optional = None
        self.disable_distutils_flag_fixing = False

    def finalize_options(self):
        dst_build_ext.build_ext.finalize_options(self)
        if self.build_optional is None:
            self.build_optional = True
        if not self.build_optional:
            self.extensions = [ext for ext in self.extensions if not isinstance(ext, OptionalExtension)] or None

    def build_extensions(self):
        if self.debug:
            # say it with me kids... distutils sucks!
            for x in ("compiler_so", "compiler", "compiler_cxx"):
                l = [y for y in getattr(self.compiler, x) if y != '-DNDEBUG']
                l.append('-Wall')
                setattr(self.compiler, x, l)
        if not self.disable_distutils_flag_fixing:
            for x in ("compiler_so", "compiler", "compiler_cxx"):
                val = getattr(self.compiler, x)
                if "-fno-strict-aliasing" not in val:
                    val.append("-fno-strict-aliasing")
        return dst_build_ext.build_ext.build_extensions(self)


class test(core.Command):

    """Run our unit tests in a built copy.

    Based on code from setuptools.
    """

    blacklist = frozenset()

    user_options = [("inplace", "i", "do building/testing in place"),
        ("skip-rebuilding", "s", "skip rebuilds. primarily for development"),
        ("disable-fork", None, "disable forking of the testloader; primarily for debugging.  "
            "Automatically set in jython, disabled for cpython/unladen-swallow."),
        ("namespaces=", "t", "run only tests matching these namespaces.  "
            "comma delimited"),
        ("pure-python", None, "disable building of extensions.  Enabled for jython, disabled elsewhere"),
        ("force", "f", "force build_py/build_ext as needed"),
        ("include-dirs=", "I", "include dirs for build_ext if needed"),
        ]

    default_test_namespace = None

    def initialize_options(self):
        self.inplace = False
        self.disable_fork = is_jython
        self.namespaces = ''
        self.pure_python = is_jython
        self.force = False
        self.include_dirs = None

    def finalize_options(self):
        self.inplace = bool(self.inplace)
        self.disable_fork = bool(self.disable_fork)
        self.pure_python = bool(self.pure_python)
        self.force = bool(self.force)
        if isinstance(self.include_dirs, str):
            self.include_dirs = self.include_dirs.split(os.pathsep)
        if self.namespaces:
            self.namespaces = tuple(set(self.namespaces.split(',')))
        else:
            self.namespaces = ()

    def run(self):
        build_ext = self.reinitialize_command('build_ext')
        build_py = self.reinitialize_command('build_py')
        build_ext.inplace = build_py.inplace = self.inplace
        build_ext.force = build_py.force = self.force

        if self.include_dirs:
            build_ext.include_dirs = self.include_dirs

        if not self.pure_python:
            self.run_command('build_ext')
        if not self.inplace:
            self.run_command('build_py')

        syspath = sys.path[:]
        mods_to_wipe = ()
        if not self.inplace:
            cwd = os.getcwd()
            syspath = [x for x in sys.path if x != cwd]
            test_path = os.path.abspath(build_py.build_lib)
            syspath.insert(0, test_path)
            mods = build_py.find_all_modules()
            mods_to_wipe = set(x[0] for x in mods)
            mods_to_wipe.update('.'.join(x[:2]) for x in mods)

        namespaces = self.namespaces
        if not self.namespaces:
            namespaces = [self.default_test_namespace]

        retval = unittest_extensions.run_tests(namespaces,
            disable_fork=self.disable_fork, blacklist=self.blacklist,
            pythonpath=syspath, modules_to_wipe=mods_to_wipe)
        if retval:
            raise errors.DistutilsExecError("tests failed; return %i" % (retval,))

# yes these are in snakeoil.compatibility; we can't rely on that module however
# since snakeoil source is in 2k form, but this module is 2k/3k compatible.
# in other words, it could be invoked by py3k to translate snakeoil to py3k
is_py3k = sys.version_info >= (3,0)
is_jython = 'java' in getattr(sys, 'getPlatform', lambda:'')().lower()

def get_number_of_processors():
    try:
        with open("/proc/cpuinfo") as f:
            val = len([x for x in f if ''.join(x.split()).split(":")[0] == "processor"])
        if not val:
            return 1
        return val
    except EnvironmentError:
        return 1


class BuildDocs(core.Command):

    user_options = [
        ('version=', None, "version we're building for"),
        ('source-dir=', None, "source directory run in"),
        ('build-dir=', None, "build directory"),
        ('builder=', None, "which sphinx builder to run.  Defaults to html"),
    ]

    def initialize_options(self):
        self.builder = None
        self.source_dir = None
        self.build_dir = None
        self.version = None

    def finalize_options(self):
        self.source_dir = os.path.abspath(self.source_dir)
        if self.build_dir is None:
            self.set_undefined_options('build', ('build_base', 'build_dir'))
            self.build_dir = os.path.join(self.build_dir, 'sphinx')
        self.build_dir = os.path.abspath(self.build_dir)

        if self.builder is None:
            self.builder = 'html'

    @staticmethod
    def find_sphinx_build():
        sphinx_build = find_executable('sphinx-build')
        if sphinx_build:
            return sphinx_build
        else:
            raise Exception("Couldn't find sphinx-build w/in PATH=%r" % os.environ.get('PATH'))

    def run(self):
        env = os.environ.copy()
        syspath = [os.path.abspath(x) for x in sys.path]
        if self.build_dir:
            syspath.insert(0, os.path.abspath(
                os.path.join(self.build_dir, '..', 'lib')))
        syspath = ':'.join(syspath)
        cmd = ['make', 'PYTHON=%s' % sys.executable, 'PYTHONPATH=%s' % syspath,
               'SPHINXBUILD=%s %s' % (sys.executable, self.find_sphinx_build()),
               str(self.builder)]
        opts = []
        if self.version:
            opts.append('-D version=%s' % self.version)
        if self.build_dir:
            cmd.append('BUILDDIR=%s' % (self.build_dir,))
        if opts:
            cmd.append('SPHINXOPTS=%s' % (' '.join(opts),))
        cwd = self.source_dir
        if not cwd:
            cwd = os.getcwd()
        if subprocess.call(cmd, cwd=cwd, env=env):
            raise errors.DistutilsExecError("doc generation failed")

    @classmethod
    def setup_kls(cls):
        try:
            from sphinx.setup_command import BuildDoc as _BuildDoc
        except ImportError:
            return None
        class BuildDoc(_BuildDoc, cls):
            _kls = _BuildDoc
            user_options = list(_BuildDoc.user_options) \
                + [('generate', None, 'force autogeneration of intermediate docs')]
            # annoying.
            for x in "initialize_options run".split():
                locals()[x] = getattr(cls, x)

        return BuildDoc


class _sphinx_missing(cmd.Command):

    user_options = []

    def initialize_options(self):
        raise errors.DistutilsExecError("sphinx is not available")


def sphinx_build_docs():
    try:
        import sphinx # pylint: disable=unused-variable
    except ImportError:
        return _sphinx_missing

    return BuildDocs
