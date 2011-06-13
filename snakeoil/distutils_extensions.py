# Copyright: 2008 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""
collection of distutils extensions adding things like automatic 2to3 translation,
a test runner, basic bzr changelog generation, and working around broken stdlib
extensions CFLAG passing in distutils.

Generally speaking, you should flip through this modules src.
"""

import os
import sys
import errno
import subprocess
import unittest


from distutils import core, ccompiler, log, errors
from distutils.command import (
    sdist as dst_sdist, build_ext as dst_build_ext, build_py as dst_build_py,
    build as dst_build)


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

    user_options = dst_sdist.sdist.user_options + [
        ('changelog', None, 'create a ChangeLog [default]'),
        ('no-changelog', None, 'do not create the ChangeLog file'),
        ('changelog-start', None, 'the bzr rev to start dumping the changelog'
            ' from; defaults to the last 5 tagged versions'),
        ]

    boolean_options = dst_sdist.sdist.boolean_options + ['changelog']

    negative_opt = {'no-changelog': 'changelog'}
    negative_opt.update(dst_sdist.sdist.negative_opt)

    default_format = dict(dst_sdist.sdist.default_format)
    default_format["posix"] = "bztar"
    default_log_format = '--short'

    package_namespace = None

    def initialize_options(self):
        dst_sdist.sdist.initialize_options(self)
        self.changelog = False
        self.changelog_start = None

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

        for prefix in ['doc', 'dev-notes']:
            self.filelist.include_pattern('.rst', prefix=prefix)
            self.filelist.exclude_pattern(os.path.sep + 'index.rst',
                                          prefix=prefix)
        self.filelist.append('build_docs.py')
        self.filelist.append('build_api_docs.sh')
        self.filelist.include_pattern('*', prefix='examples')
        self.filelist.include_pattern('*', prefix='bin')

        self._add_to_file_list()

        if self.prune:
            self.prune_file_list()

        # This is not optional: remove_duplicates needs sorted input.
        self.filelist.sort()
        self.filelist.remove_duplicates()

    def _add_to_file_list(self):
        pass

    def find_last_tags_back(self, last_n_tags=5, majors_only=False):
        p = subprocess.Popen(['bzr', 'tags', '--sort=time'],
            stdout=subprocess.PIPE)
        data = [x.split() for x in p.stdout if x]
        data_d = dict(data)
        if not p.returncode != 0:
            raise errors.DistutilsExecError("bzr tags returned non zero: %r"
                % (p.returncode,))
        seen = set()
        tags = []
        for tag, revno in data:
            tag_targ = tag
            if majors_only:
                tag_targ = '.'.join(tag.split(".")[:2])
            if tag_targ not in seen:
                seen.add(tag_targ)
                tags.append((tag_targ, tag, revno))
        tags = tags[max(len(tags) - last_n_tags, 0):]
        return 'tag:%s' % (tags[0][1],)

    def generate_verinfo(self, base_dir):
        log.info('generating _verinfo')
        from snakeoil.version import get_git_version
        val = get_git_version(base_dir)
        open(os.path.join(base_dir, self.package_namespace, '_verinfo.py'), 'w').write(
            'version_info="""%s"""\n' % (val.strip(),))

    def make_release_tree(self, base_dir, files):
        """Create and populate the directory tree that is put in source tars.

        This copies or hardlinks "normal" source files that should go
        into the release and adds generated files that should not
        exist in a working tree.
        """
        dst_sdist.sdist.make_release_tree(self, base_dir, files)
        if self.changelog:
            args = []
            if not self.changelog_start:
                self.changelog_start = self.find_last_tags_back()
            if self.changelog_start:
                args += ['-r', '%s..' % (self.changelog_start,),
                    '--include-merge']
            if self.default_log_format:
                args += [self.default_log_format]
            log.info("regenning ChangeLog to %r (may take a while)" %
                (self.changelog_start,))
            if subprocess.call(
                [bzrbin, 'log', '--verbose'] + args,
                stdout=open(os.path.join(base_dir, 'ChangeLog'), 'w')):
                raise errors.DistutilsExecError('bzr log failed')
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
    generate_bzr_ver = True

    def initialize_options(self):
        dst_build_py.build_py.initialize_options(self)
        self.inplace = False

    def finalize_options(self):
        self.inplace = bool(self.inplace)
        if self.inplace:
            self.build_lib = '.'
        dst_build_py.build_py.finalize_options(self)

    def _compute_py3k_rebuilds(self, force=False):
        pjoin = os.path.join
        for base, mod_name, path in self.find_all_modules():
            try:
                new_mtime = os.lstat(path).st_mtime
            except EnvironmentError:
                # ok... wtf distutils?
                continue
            trg_path = pjoin(self.build_lib, path)
            if force:
                yield trg_path, new_mtime
                continue
            try:
                old_mtime = os.lstat(trg_path).st_mtime
            except EnvironmentError:
                yield trg_path, new_mtime
                continue
            if old_mtime != new_mtime:
                yield trg_path, new_mtime

    def _inner_run(self, py3k_rebuilds):
        pass

    def _run_generate_bzr_ver(self, py3k_rebuilds):
        bzr_ver = self.get_module_outfile(
            self.build_lib, (self.package_namespace,), 'bzr_verinfo')
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

    def get_py2to3_converter(self, options=None, proc_count=0):
        from lib2to3 import refactor as ref_mod
        from snakeoil import caching_2to3

        if proc_count == 0:
            proc_count = get_number_of_processors()
        if proc_count and (sys.version_info >= (3,0) and sys.version_info < (3,1,2)) or \
            (sys.version_info >=  (2,6) and sys.version_info < (2,6,5)):
            log.warn("disabling parallelization: you're running a python "
                "version with a broken multiprocessing.queue.JoinableQueue.put "
                "(python bug 4660).")
            proc_count = 1

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

        if self.generate_bzr_ver:
            self._run_generate_bzr_ver(py3k_rebuilds)

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


class TestLoader(unittest.TestLoader):

    """Test loader that knows how to recurse packages."""

    def __init__(self, blacklist):
        self.blacklist = blacklist
        unittest.TestLoader.__init__(self)

    def loadTestsFromModule(self, module):
        """Recurses if module is actually a package."""
        paths = getattr(module, '__path__', None)
        tests = [unittest.TestLoader.loadTestsFromModule(self, module)]
        if paths is None:
            # Not a package.
            return tests[0]
        if module.__name__ in self.blacklist:
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

            if not self.disable_fork:
                # thank you for binding freaking sys.stderr into your prototype
                # unittest...
                sys.stderr.flush()
                os.dup2(sys.stdout.fileno(), sys.stderr.fileno())
            args = ['setup.py', '-v']
            if self.namespaces:
                args.extend(self.namespaces)
                default_mod = None
            else:
                default_mod = self.default_test_namespace
            unittest.main(default_mod, argv=args,
                testLoader=TestLoader(self.blacklist))
            if not self.disable_fork:
                os._exit(1)
            return
        retval = os.waitpid(pid, 0)[1]
        if retval:
            raise errors.DistutilsExecError("tests failed; return %i" % (retval,))

# yes these are in snakeoil.compatibility; we can't rely on that module however
# since snakeoil source is in 2k form, but this module is 2k/3k compatible.
# in other words, it could be invoked by py3k to translate snakeoil to py3k
is_py3k = sys.version_info >= (3,0)
is_jython = 'java' in getattr(sys, 'getPlatform', lambda:'')().lower()

def get_number_of_processors():
    try:
        val = len([x for x in open("/proc/cpuinfo") if ''.join(x.split()).split(":")[0] == "processor"])
        if not val:
            return 1
        return val
    except EnvironmentError:
        return 1
