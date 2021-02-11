"""
A collection of distutils extensions adding things like automatic 2to3
translation, a test runner, and working around broken stdlib extensions CFLAG
passing in distutils.

Specifically, this module is only meant to be imported in setup.py scripts.
"""

from contextlib import contextmanager, redirect_stdout, redirect_stderr, ExitStack
import copy
from datetime import datetime
import errno
import inspect
import math
from multiprocessing import cpu_count
import operator
import os
import re
import shlex
import shutil
import subprocess
import sys
import textwrap

from setuptools import find_packages
from setuptools.command import install as dst_install

from distutils import log
from distutils.core import Command, Extension
from distutils.errors import DistutilsExecError, DistutilsError
from distutils.command import (
    sdist as dst_sdist, build_ext as dst_build_ext, build_py as dst_build_py,
    build as dst_build, build_scripts as dst_build_scripts, config as dst_config)


# forcibly disable lazy module loading
os.environ['SNAKEOIL_DEMANDIMPORT'] = 'false'

# top level repo/tarball directory
REPODIR = os.environ.get('PKGDIST_REPODIR')
if REPODIR is None:
    # hack to verify we're running under a setup.py script and grab its info
    for _frameinfo in reversed(inspect.stack(0)):
        _filename = _frameinfo[1]
        if os.path.basename(_filename) == 'setup.py':
            REPODIR = os.path.dirname(os.path.abspath(_filename))
            break
    else:
        raise ImportError('this module is only meant to be imported in setup.py scripts')

# running under pip
PIP = os.path.basename(os.environ.get('_', '')) == 'pip' or REPODIR.split(os.sep)[2].startswith('pip-')

# executable scripts directory
SCRIPTS_DIR = os.path.join(REPODIR, 'bin')


def find_moduledir(searchdir=REPODIR):
    """Determine a module's directory path.

    Based on the assumption that the project is only distributing one main
    module.
    """
    modules = []
    moduledir = None
    searchdir_depth = len(searchdir.split('/'))
    # allow modules to be found inside a top-level dir, e.g. 'src'
    searchdir_depth += 1

    # look for a top-level module
    for root, dirs, files in os.walk(searchdir):
        # only descend to a specified level
        if len(root.split('/')) > searchdir_depth + 1:
            continue
        if '__init__.py' in files:
            # only match modules with __title__ defined in the main module
            with open(os.path.join(root, '__init__.py'), encoding='utf-8') as f:
                try:
                    if re.search(r'^__title__\s*=\s*[\'"]([^\'"]*)[\'"]',
                                 f.read(), re.MULTILINE):
                        modules.append(root)
                except AttributeError:
                    continue

    if len(modules) == 1:
        moduledir = modules[0]
    elif len(modules) > 1:
        raise ValueError(
            'Multiple main modules found in %r: %s' % (
                searchdir, ', '.join(os.path.basename(x) for x in modules)))

    if moduledir is None:
        raise ValueError('No main module found')

    return moduledir


# determine the main module we're being used to package
MODULEDIR = find_moduledir()
PACKAGEDIR = os.path.dirname(MODULEDIR)
MODULE_NAME = os.path.basename(MODULEDIR)

# running against git/unreleased version
GIT = not os.path.exists(os.path.join(PACKAGEDIR, '_verinfo.py'))


def module_version(moduledir=MODULEDIR):
    """Determine a module's version.

    Based on the assumption that a module defines __version__.
    """
    version = None
    try:
        with open(os.path.join(moduledir, '__init__.py'), encoding='utf-8') as f:
            version = re.search(
                r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
                f.read(), re.MULTILINE).group(1)
    except IOError as e:
        if e.errno == errno.ENOENT:
            pass
        else:
            raise

    if version is None:
        raise RuntimeError(f'Cannot find version for module: {MODULE_NAME}')

    # use versioning scheme similar to setuptools_scm for untagged versions
    git_version = get_git_version(REPODIR)
    if git_version:
        tag = git_version['tag']
        if tag is None:
            commits = git_version['commits']
            rev = git_version['rev'][:7]
            date = datetime.strptime(git_version['date'], '%a, %d %b %Y %H:%M:%S %z')
            date = datetime.strftime(date, '%Y%m%d')
            if commits is not None:
                version += f'.dev{commits}'
            version += f'+g{rev}.d{date}'
        elif tag != version:
            raise DistutilsError(
                f'unmatched git tag {tag!r} and {MODULE_NAME} version {version!r}')

    return version


def generate_verinfo(target_dir):
    """Generate project version module.

    This is used by the --version option in interactive programs among
    other things.
    """
    data = get_git_version(REPODIR)
    path = os.path.join(target_dir, '_verinfo.py')
    log.info(f'generating version info: {path}')
    with open(path, 'w') as f:
        f.write('version_info=%r' % (data,))
    return path


def readme(topdir=REPODIR):
    """Determine a project's long description."""
    for doc in ('README.rst', 'README'):
        try:
            with open(os.path.join(topdir, doc), encoding='utf-8') as f:
                return f.read()
        except IOError as e:
            if e.errno == errno.ENOENT:
                pass
            else:
                raise

    return None


def setup():
    """Parameters and commands for setuptools."""
    # pip installing from git forces development versions to be used
    if PIP and GIT:
        install_deps = _requires('dev.txt')
    else:
        install_deps = _requires('install.txt')

    params = {
        'name': MODULE_NAME,
        'version': module_version(),
        'long_description': readme(),
        'packages': find_packages(PACKAGEDIR),
        'package_dir': {'': os.path.basename(PACKAGEDIR)},
        'install_requires': install_deps,
        'tests_require': _requires('test.txt'),
        'python_requires': '>=3.8',
    }

    cmds = {
        'sdist': sdist,
        'build_py': build_py,
        'test': pytest,
    }

    # check for scripts
    if os.path.exists(SCRIPTS_DIR):
        params['scripts'] = os.listdir(SCRIPTS_DIR)
        cmds['build_scripts'] = build_scripts

    docdir = os.path.join(REPODIR, 'doc')
    doc = os.path.exists(docdir)
    mandir = os.path.join(REPODIR, 'doc', 'man')
    man = os.path.exists(mandir)

    if doc or man:
        cmds['build'] = build
        cmds['build_docs'] = build_docs
        cmds['install_docs'] = install_docs

    # check for docs
    if doc:
        cmds['build_html'] = build_html
        cmds['install_html'] = install_html

    # check for man pages
    if man:
        cmds['build_man'] = build_man
        cmds['install_man'] = install_man

    return params, cmds


def _requires(filename):
    """Determine a project's various dependencies from requirements files."""
    try:
        with open(os.path.join(REPODIR, 'requirements', filename)) as f:
            return f.read().splitlines()
    except FileNotFoundError:
        pass
    return None


def get_file_paths(path):
    """Get list of all file paths under a given path."""
    for root, dirs, files in os.walk(path):
        for f in files:
            yield os.path.join(root, f)[len(path):].lstrip('/')


def data_mapping(host_prefix, path, skip=None):
    """Map repo paths to host paths for installed data files."""
    skip = list(skip) if skip is not None else []
    for root, dirs, files in os.walk(path):
        host_path = os.path.join(host_prefix, root.partition(path)[2].lstrip('/'))
        repo_path = os.path.join(path, root.partition(path)[2].lstrip('/'))
        if repo_path not in skip:
            yield (host_path, [os.path.join(root, x) for x in files
                               if os.path.join(root, x) not in skip])


def pkg_config(*packages, **kw):
    """Translate pkg-config data to compatible Extension parameters.

    Example usage:

    >>> from distutils.extension import Extension
    >>> from pkgdist import pkg_config
    >>>
    >>> ext_kwargs = dict(
    ...     include_dirs=['include'],
    ...     extra_compile_args=['-std=c++11'],
    ... )
    >>> extensions = [
    ...     Extension('foo', ['foo.c']),
    ...     Extension('bar', ['bar.c'], **pkg_config('lcms2')),
    ...     Extension('ext', ['ext.cpp'], **pkg_config(('nss', 'libusb-1.0'), **ext_kwargs)),
    ... ]
    """
    flag_map = {
        '-I': 'include_dirs',
        '-L': 'library_dirs',
        '-l': 'libraries',
    }

    try:
        tokens = subprocess.check_output(
            ['pkg-config', '--libs', '--cflags'] + list(packages)).split()
    except OSError as e:
        sys.stderr.write(f'running pkg-config failed: {e.strerror}\n')
        sys.exit(1)

    for token in tokens:
        token = token.decode()
        if token[:2] in flag_map:
            kw.setdefault(flag_map.get(token[:2]), []).append(token[2:])
        else:
            kw.setdefault('extra_compile_args', []).append(token)
    return kw


def cython_pyx(path=MODULEDIR):
    """Return all available cython extensions under a given path."""
    for root, _dirs, files in os.walk(path):
        for f in files:
            if f.endswith('.pyx'):
                yield str(os.path.join(root, f))


def cython_exts(build_deps=None, build_exts=None, build_opts=None, path=MODULEDIR):
    """Prepare all cython extensions under a given path to be built."""
    build_deps = build_deps if build_deps is not None else []
    build_exts = build_exts if build_exts is not None else []
    build_opts = build_opts if build_opts is not None else {}

    exts = []
    cython_exts = []

    for ext in cython_pyx(path):
        cythonized = os.path.splitext(ext)[0] + '.c'
        if os.path.exists(cythonized):
            exts.append(cythonized)
        else:
            cython_exts.append(ext)

    # require cython to build exts as necessary
    if cython_exts:
        build_deps.append('cython')
        exts.extend(cython_exts)

    for ext in exts:
        # strip package dir
        module = ext.rpartition(PACKAGEDIR)[-1].lstrip(os.path.sep)
        # strip file extension and translate to module namespace
        module = os.path.splitext(module)[0].replace(os.path.sep, '.')
        build_exts.append(Extension(module, [ext], **build_opts))

    return build_deps, build_exts


class OptionalExtension(Extension):
    """Python extension that is optional to build.

    If it's not required to have the exception built, just preferable,
    use this class instead of :py:class:`Extension` since the machinery
    in this module relies on isinstance to identify what absolutely must
    be built vs what would be nice to have built.
    """
    pass


class sdist(dst_sdist.sdist):
    """sdist command wrapper to bundle generated files for release."""

    def initialize_options(self):
        dst_sdist.sdist.initialize_options(self)

    def make_release_tree(self, base_dir, files):
        """Create and populate the directory tree that is put in source tars.

        This copies or hardlinks "normal" source files that should go
        into the release and adds generated files that should not
        exist in a working tree.
        """

        # don't build man pages when running under tox
        if ('build_man' in self.distribution.cmdclass and
                not os.path.basename(os.environ.get('_', '')) == 'tox'):
            build_man = self.reinitialize_command('build_man')
            # force sphinx to run at our chosen verbosity
            build_man.verbosity = self.verbose
            build_man.ensure_finalized()
            self.run_command('build_man')
            shutil.copytree(os.path.join(os.getcwd(), build_man.content_search_path[0]),
                            os.path.join(base_dir, build_man.content_search_path[1]))

        dst_sdist.sdist.make_release_tree(self, base_dir, files)
        build_py = self.reinitialize_command('build_py')
        build_py.ensure_finalized()
        generate_verinfo(os.path.join(
            base_dir, build_py.package_dir.get('', ''), MODULE_NAME))

    def run(self):
        build_ext = self.reinitialize_command('build_ext')
        build_ext.ensure_finalized()

        # generate cython extensions if any exist
        extensions = list(cython_pyx())
        if extensions:
            from Cython.Build import cythonize
            cythonize(extensions, nthreads=cpu_count())

        dst_sdist.sdist.run(self)


class build_py(dst_build_py.build_py):
    """build_py command wrapper."""

    user_options = dst_build_py.build_py.user_options + \
        [("inplace", "i", "do any source conversions in place")]

    generate_verinfo = True

    def initialize_options(self):
        dst_build_py.build_py.initialize_options(self)
        self.inplace = False

    def finalize_options(self):
        self.inplace = bool(self.inplace)
        if self.inplace:
            self.build_lib = '.'
        dst_build_py.build_py.finalize_options(self)

    def _run_generate_verinfo(self, rebuilds=None):
        ver_path = generate_verinfo(os.path.join(self.build_lib, MODULE_NAME))
        self.byte_compile([ver_path])
        if rebuilds is not None:
            rebuilds.append((ver_path, os.lstat(ver_path).st_mtime))

    def run(self):
        dst_build_py.build_py.run(self)

        if self.generate_verinfo:
            self._run_generate_verinfo()


def generate_html():
    """Generate html docs for the project."""
    from snakeoil.dist.generate_docs import generate_html
    generate_html(REPODIR, PACKAGEDIR, MODULE_NAME)


def generate_man():
    """Generate man pages for the project."""
    from snakeoil.dist.generate_docs import generate_man
    generate_man(REPODIR, PACKAGEDIR, MODULE_NAME)


class build_docs(Command):
    """Generic documentation build command."""

    # use custom verbosity option since distutils appears to
    # statically assign the default verbose option
    user_options = [
        ('force', 'f', 'force build as needed'),
        ('verbosity', 'v', 'run verbosely (default disabled)'),
    ]

    content_search_path = ()
    sphinx_targets = None

    def initialize_options(self):
        self.force = False
        self.verbosity = 0

    def finalize_options(self):
        self.force = bool(self.force)
        self.verbosity = int(bool(self.verbosity))

    @property
    def skip(self):
        # don't rebuild if one of the output dirs exist
        if any(os.path.exists(x) for x in self.content_search_path):
            log.info(f'{self.__class__.__name__}: already built, skipping regeneration...')
            return True
        return False

    def _generate_doc_content(self):
        """Hook to generate custom doc content used by sphinx."""

    def build(self):
        if self.force or not self.skip:
            # TODO: report this to upstream sphinx
            # Workaround for sphinx doing include directive path mangling in
            # order to interpret absolute paths "correctly", but at the same
            # time causing relative paths to fail. This just bypasses the
            # sphinx mangling and lets docutils handle include directives
            # directly which works as expected.
            from docutils.parsers.rst.directives.misc import Include as BaseInclude
            from sphinx.directives.other import Include
            Include.run = BaseInclude.run

            # Use a built version for the man page generation process that
            # imports script modules.
            build_py = self.reinitialize_command('build_py')
            build_py.ensure_finalized()
            self.run_command('build_py')

            # Override the module search path before running sphinx. This fixes
            # generating man pages for scripts that need to import modules
            # generated via 2to3 or other conversions instead of straight from
            # the build directory.
            with syspath(os.path.abspath(build_py.build_lib)):
                # Generating man pages with sphinx is unnecessarily noisy by
                # default since sphinx assumes files are laid out in a manner
                # for technical doc generation. Therefore, suppress all stderr
                # by default unless verbose mode is enabled.
                with suppress(self.verbosity):
                    self._generate_doc_content()
                    for target in self.sphinx_targets:
                        build_sphinx = self.reinitialize_command('build_sphinx')
                        build_sphinx.builder = target
                        build_sphinx.ensure_finalized()
                        self.run_command('build_sphinx')

    def run(self):
        if self.sphinx_targets:
            # run regular build
            self.build()
        else:
            # build all docs
            for target in ('man', 'html'):
                cmd = f'build_{target}'
                build_cmd = self.reinitialize_command(cmd)
                build_cmd.ensure_finalized()
                build_cmd.build()


class build_man(build_docs):
    """Build man pages."""

    description = "build man pages"
    content_search_path = ('build/sphinx/man', 'man')
    sphinx_targets = ('man',)

    def _generate_doc_content(self):
        # generate man page content for scripts we create
        if 'build_scripts' in self.distribution.cmdclass:
            generate_man()


class build_html(build_docs):
    """Build html docs."""

    description = "build HTML documentation"
    content_search_path = ('build/sphinx/html', 'html')
    sphinx_targets = ('html',)

    def _generate_doc_content(self):
        # generate man pages -- html versions of man pages are provided
        self.run_command('build_man')

        # generate API docs
        generate_html()


class build_ext(dst_build_ext.build_ext):
    """Build native extensions."""

    user_options = dst_build_ext.build_ext.user_options + [
        ("build-optional=", "o", "build optional C modules"),
        ("disable-distutils-flag-fixing", None,
         "disable fixing of issue 969718 in python, adding missing -fno-strict-aliasing"),
    ]

    boolean_options = dst_build.build.boolean_options + ["build-optional"]

    def initialize_options(self):
        dst_build_ext.build_ext.initialize_options(self)
        self.build_optional = None
        self.disable_distutils_flag_fixing = False
        self.default_header_install_dir = None

    def finalize_options(self):
        dst_build_ext.build_ext.finalize_options(self)
        if self.build_optional is None:
            self.build_optional = True
        self.build_optional = bool(self.build_optional)
        if not self.build_optional:
            self.extensions = [ext for ext in self.extensions if not isinstance(ext, OptionalExtension)]

        # add header install dir to the search path
        # (fixes virtualenv builds for consumer extensions)
        self.set_undefined_options(
            'install',
            ('install_headers', 'default_header_install_dir'))
        if self.default_header_install_dir:
            self.default_header_install_dir = os.path.dirname(self.default_header_install_dir)
            for e in self.extensions:
                # include_dirs may actually be shared between multiple extensions
                if self.default_header_install_dir not in e.include_dirs:
                    e.include_dirs.append(self.default_header_install_dir)

    @staticmethod
    def determine_ext_lang(ext_path):
        """Determine file extensions for generated cython extensions."""
        with open(ext_path) as f:
            for line in f:
                line = line.lstrip()
                if not line:
                    continue
                elif line[0] != '#':
                    return None
                line = line[1:].lstrip()
                if line[:10] == 'distutils:':
                    key, _, value = [s.strip() for s in line[10:].partition('=')]
                    if key == 'language':
                        return value
            else:
                return None

    def no_cythonize(self):
        """Determine file paths for generated cython extensions."""
        extensions = copy.deepcopy(self.extensions)
        for extension in extensions:
            sources = []
            for sfile in extension.sources:
                path, ext = os.path.splitext(sfile)
                if ext in ('.pyx', '.py'):
                    lang = build_ext.determine_ext_lang(sfile)
                    if lang == 'c++':
                        ext = '.cpp'
                    else:
                        ext = '.c'
                    sfile = path + ext
                sources.append(sfile)
            extension.sources[:] = sources
        return extensions

    def run(self):
        # ensure that the platform checks were performed
        self.run_command('config')

        # only regenerate cython extensions if requested or required
        use_cython = (
            os.environ.get('USE_CYTHON', False) or
            any(not os.path.exists(x) for ext in self.no_cythonize() for x in ext.sources))
        if use_cython:
            from Cython.Build import cythonize
            cythonize(self.extensions, nthreads=cpu_count())

        self.extensions = self.no_cythonize()
        return dst_build_ext.build_ext.run(self)

    def build_extensions(self):
        # say it with me kids... distutils sucks!
        for x in ("compiler_so", "compiler", "compiler_cxx"):
            if self.debug:
                l = [y for y in getattr(self.compiler, x) if y != '-DNDEBUG']
                l.append('-Wall')
                setattr(self.compiler, x, l)
            if not self.disable_distutils_flag_fixing:
                val = getattr(self.compiler, x)
                if "-fno-strict-aliasing" not in val:
                    val.append("-fno-strict-aliasing")
            if getattr(self.distribution, 'check_defines', None):
                val = getattr(self.compiler, x)
                for d, result in self.distribution.check_defines.items():
                    if result:
                        val.append(f'-D{d}=1')
                    else:
                        val.append(f'-U{d}')
        return dst_build_ext.build_ext.build_extensions(self)


class build_scripts(dst_build_scripts.build_scripts):
    """Create and build (copy and modify shebang lines) wrapper scripts."""

    def finalize_options(self):
        dst_build_scripts.build_scripts.finalize_options(self)
        script_dir = os.path.join(
            os.path.dirname(self.build_dir), '.generated_scripts')
        self.mkpath(script_dir)
        self.scripts = [os.path.join(script_dir, x) for x in os.listdir(SCRIPTS_DIR)]

    def run(self):
        for script in self.scripts:
            with open(script, 'w') as f:
                f.write(textwrap.dedent(f"""\
                    #!{sys.executable}
                    from os.path import basename
                    from {MODULE_NAME} import scripts
                    scripts.run(basename(__file__))
                """))
        self.copy_scripts()


class build(dst_build.build):
    """Generic build command."""

    user_options = dst_build.build.user_options[:]
    user_options.append(('enable-man-pages', None, 'build man pages'))
    user_options.append(('enable-html-docs', None, 'build html docs'))

    boolean_options = dst_build.build.boolean_options[:]
    boolean_options.extend(['enable-man-pages', 'enable-html-docs'])

    sub_commands = dst_build.build.sub_commands[:]
    sub_commands.append(('build_ext', None))
    sub_commands.append(('build_py', None))
    sub_commands.append(('build_scripts', None))
    sub_commands.append(('build_man', operator.attrgetter('enable_man_pages')))
    sub_commands.append(('build_html', operator.attrgetter('enable_html_docs')))

    def initialize_options(self):
        dst_build.build.initialize_options(self)
        self.enable_man_pages = False
        self.enable_html_docs = False

    def finalize_options(self):
        dst_build.build.finalize_options(self)
        if self.enable_man_pages is None:
            path = os.path.dirname(os.path.abspath(__file__))
            self.enable_man_pages = not os.path.exists(os.path.join(path, 'man'))

        if self.enable_html_docs is None:
            self.enable_html_docs = False


class install_docs(Command):
    """Generic documentation install command."""

    content_search_path = ()
    description = "install documentation"
    user_options = [
        ('build-dir=', None, 'build directory'),
        ('docdir=', None, 'override docs install path'),
        ('htmldir=', None, 'override html install path'),
        ('mandir=', None, 'override man install path'),
    ]
    build_command = None

    def initialize_options(self):
        self.root = None
        self.prefix = None
        self.docdir = None
        self.htmldir = None
        self.mandir = None
        self.build_dir = None

    def finalize_options(self):
        self.set_undefined_options(
            'install',
            ('root', 'root'),
            ('install_base', 'prefix'),
        )
        if not self.root:
            self.root = '/'
        if self.docdir is None:
            self.docdir = os.path.join(
                self.prefix, 'share', 'doc',
                MODULE_NAME + f'-{module_version()}',
            )
        if self.htmldir is None:
            self.htmldir = os.path.join(self.docdir, 'html')
        if self.mandir is None:
            self.mandir = os.path.join(self.prefix, 'share', 'man')

    def find_content(self):
        """Determine if generated doc files exist."""
        for possible_path in self.content_search_path:
            if self.build_dir is not None:
                possible_path = os.path.join(self.build_dir, possible_path)
            possible_path = os.path.join(REPODIR, possible_path)
            if os.path.isdir(possible_path):
                return possible_path
        else:
            return None

    def _map_paths(self, content):
        """Map doc files to install paths."""
        return {x: x for x in content}

    @property
    def install_dir(self):
        """Target install directory."""
        return self.docdir

    def install(self):
        """Install docs to target dirs."""
        source_path = self.find_content()
        if source_path is None:
            raise DistutilsExecError('no generated sphinx content')

        # determine mapping from doc files to install paths
        content = self._map_paths(get_file_paths(source_path))

        # create directories
        directories = set(map(os.path.dirname, content.values()))
        directories.discard('')
        for x in sorted(directories):
            self.mkpath(os.path.join(self.install_dir, x))

        # copy docs over
        for src, dst in sorted(content.items()):
            self.copy_file(
                os.path.join(source_path, src),
                os.path.join(self.install_dir, dst))

    def run(self):
        if self.build_command is not None:
            # run regular install, rebuilding as necessary
            try:
                self.install()
            except DistutilsExecError:
                self.run_command(self.build_command)
                self.install()
        else:
            # install all docs that have been generated
            for target in ('man', 'html'):
                cmd = f'install_{target}'
                install_cmd = self.reinitialize_command(cmd)
                install_cmd.docdir = self.docdir
                install_cmd.htmldir = self.htmldir
                install_cmd.mandir = self.mandir
                install_cmd.ensure_finalized()
                try:
                    install_cmd.install()
                except DistutilsExecError:
                    log.info(f'built {target} pages missing, skipping install')


class install_html(install_docs):
    """Install html documentation."""

    content_search_path = build_html.content_search_path
    description = "install HTML documentation"
    build_command = 'build_html'

    @property
    def install_dir(self):
        return self.htmldir


class install_man(install_docs):
    """Install man pages."""

    description = "install man pages"
    content_search_path = build_man.content_search_path
    build_command = 'build_man'

    @property
    def install_dir(self):
        return self.mandir

    def _map_paths(self, content):
        d = {}
        for x in content:
            if len(x) >= 3 and x[-2] == '.' and x[-1].isdigit():
                # Only consider extensions .1, .2, .3, etc, and files that
                # have at least a single char beyond the extension (thus ignore
                # .1, but allow a.1).
                d[x] = f'man{x[-1]}/{os.path.basename(x)}'
        return d


class install(dst_install.install):
    """Generic install command."""

    user_options = dst_install.install.user_options[:]
    user_options.extend([
        ('enable-man-pages', None, 'install man pages'),
        ('enable-html-docs', None, 'install html docs'),
        ('docdir=', None, 'override docs install path'),
        ('htmldir=', None, 'override html install path'),
        ('mandir=', None, 'override man install path'),
    ])

    boolean_options = dst_install.install.boolean_options[:]
    boolean_options.extend(['enable-man-pages', 'enable-html-docs'])

    def initialize_options(self):
        dst_install.install.initialize_options(self)
        self.enable_man_pages = False
        self.enable_html_docs = False
        self.docdir = None
        self.htmldir = None
        self.mandir = None

    def finalize_options(self):
        build_options = self.distribution.command_options.setdefault('build', {})
        build_options['enable_html_docs'] = ('command_line', self.enable_html_docs and 1 or 0)
        man_pages = self.enable_man_pages
        if man_pages and os.path.exists('man'):
            man_pages = False
        build_options['enable_man_pages'] = ('command_line', man_pages and 1 or 0)
        dst_install.install.finalize_options(self)

    sub_commands = dst_install.install.sub_commands[:]
    sub_commands.append(('install_man', operator.attrgetter('enable_man_pages')))
    sub_commands.append(('install_html', operator.attrgetter('enable_html_docs')))

    def run(self):
        super().run()

        # don't install docs by default
        if self.enable_man_pages:
            install_man = self.reinitialize_command('install_man')
            if install_man.find_content() is None:
                raise DistutilsError("built man pages missing")
            else:
                install_man.docdir = self.docdir
                install_man.mandir = self.mandir
                install_man.ensure_finalized()
                self.run_command('install_man')

        if self.enable_html_docs:
            install_html = self.reinitialize_command('install_html')
            if install_html.find_content() is None:
                raise DistutilsError("built html docs missing")
            else:
                install_html.docdir = self.docdir
                install_html.htmldir = self.htmldir
                install_html.ensure_finalized()
                self.run_command('install_html')


class test(Command):
    """Run our unit tests in a built copy.

    Based on code from setuptools.
    """

    blacklist = frozenset()

    description = "run unit tests in a built copy"
    user_options = [
        ("inplace", "i", "do building/testing in place"),
        ("skip-rebuilding", "s", "skip rebuilds. primarily for development"),
        ("disable-fork", None, "disable forking of the testloader; primarily for debugging"),
        ("namespaces=", "t", "run only tests matching these namespaces.  "
                             "comma delimited"),
        ("pure-python", None, "disable building of extensions"),
        ("force", "f", "force build_py/build_ext as needed"),
        ("include-dirs=", "I", "include dirs for build_ext if needed"),
    ]

    default_test_namespace = f'{MODULE_NAME}.test'

    def initialize_options(self):
        self.inplace = False
        self.disable_fork = False
        self.namespaces = ''
        self.pure_python = False
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
        from snakeoil.dist import unittest_extensions

        build_ext = self.reinitialize_command('build_ext')
        build_py = self.reinitialize_command('build_py')
        build_ext.inplace = build_py.inplace = self.inplace
        build_ext.force = build_py.force = self.force
        build_ext.ensure_finalized()
        build_py.ensure_finalized()

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

        retval = unittest_extensions.run_tests(
            namespaces, disable_fork=self.disable_fork,
            blacklist=self.blacklist, pythonpath=syspath,
            modules_to_wipe=mods_to_wipe)

        # remove temporary plugincache so it isn't installed
        plugincache = os.path.join(
            os.path.abspath(build_py.build_lib), MODULE_NAME,
            'plugins/plugincache')
        if os.path.exists(plugincache):
            os.remove(plugincache)

        if retval:
            raise DistutilsExecError("tests failed; return %i" % (retval,))


class pytest(Command):
    """Run tests using pytest."""

    description = "run unit tests in a built copy using pytest"
    user_options = [
        ('pytest-args=', 'a', 'arguments to pass to py.test'),
        ('coverage', 'c', 'generate coverage info'),
        ('skip-build', 's', 'skip building the module'),
        ('test-dir=', 'd', 'directory to source tests from'),
        ('report=', 'r', 'generate and/or show a coverage report'),
        ('jobs=', 'j', 'run X parallel tests at once'),
        ('match=', 'k', 'run only tests that match the provided expressions'),
        ('targets=', 't', 'target tests to run'),
    ]

    def initialize_options(self):
        self.pytest_args = ''
        self.coverage = False
        self.skip_build = False
        self.test_dir = None
        self.match = None
        self.targets = None
        self.jobs = None
        self.report = None

    def finalize_options(self):
        # if a test dir isn't specified explicitly try to find one
        if self.test_dir is None:
            for path in (os.path.join(REPODIR, 'test', 'module'),
                         os.path.join(REPODIR, 'test'),
                         os.path.join(REPODIR, 'tests', 'module'),
                         os.path.join(REPODIR, 'tests'),
                         os.path.join(MODULEDIR, 'test'),
                         os.path.join(MODULEDIR, 'tests')):
                if os.path.exists(path):
                    self.test_dir = path
                    break
            else:
                raise DistutilsExecError('cannot automatically determine test directory')

        self.test_args = []
        if self.targets is not None:
            targets = [os.path.join(self.test_dir, x) for x in self.targets.split()]
            self.test_args.extend(targets)
        else:
            self.test_args.append(self.test_dir)
        self.coverage = bool(self.coverage)
        self.skip_build = bool(self.skip_build)
        if self.verbose:
            self.test_args.append('-v')
        if self.match is not None:
            self.test_args.extend(['-k', self.match])

        if self.coverage or self.report:
            try:
                import pytest_cov
                self.test_args.extend(['--cov', MODULE_NAME])
            except ImportError:
                raise DistutilsExecError('install pytest-cov for coverage support')

            coveragerc = os.path.join(REPODIR, '.coveragerc')
            if os.path.exists(coveragerc):
                self.test_args.extend(['--cov-config', coveragerc])

            if self.report is None:
                # disable coverage report output
                self.test_args.extend(['--cov-report='])
            else:
                self.test_args.extend(['--cov-report', self.report])

        if self.jobs is not None:
            try:
                import xdist
                self.test_args.extend(['-n', self.jobs])
            except ImportError:
                raise DistutilsExecError('install pytest-xdist for -j/--jobs support')

        # add custom pytest args
        self.test_args.extend(shlex.split(self.pytest_args))

    def run(self):
        try:
            import pytest
        except ImportError:
            raise DistutilsExecError('pytest is not installed')

        if self.skip_build:
            builddir = MODULEDIR
        else:
            # build extensions and byte-compile python
            build_ext = self.reinitialize_command('build_ext')
            build_py = self.reinitialize_command('build_py')
            build_ext.ensure_finalized()
            build_py.ensure_finalized()
            self.run_command('build_ext')
            self.run_command('build_py')
            builddir = os.path.abspath(build_py.build_lib)

        # force reimport of project from builddir
        sys.modules.pop(MODULE_NAME, None)

        with syspath(builddir):
            from snakeoil.contexts import chdir
            # Change the current working directory to the builddir during testing
            # so coverage paths are correct.
            with chdir(builddir):
                ret = pytest.main(self.test_args)
        sys.exit(ret)


class pylint(Command):
    """Run pylint on a module."""

    description = "run pylint on a module"
    user_options = [
        ('errors-only', 'E', 'Check only errors with pylint'),
        ('output-format=', 'f', 'Change the output format'),
    ]

    def initialize_options(self):
        self.errors_only = False
        self.output_format = 'colorized'

    def finalize_options(self):
        self.errors_only = bool(self.errors_only)

    def run(self):
        try:
            from pylint import lint
        except ImportError:
            raise DistutilsExecError('pylint is not installed')

        lint_args = [MODULEDIR]
        rcfile = os.path.join(REPODIR, '.pylintrc')
        if os.path.exists(rcfile):
            lint_args.extend(['--rcfile', rcfile])
        if self.errors_only:
            lint_args.append('-E')
        lint_args.extend(['--output-format', self.output_format])
        lint.Run(lint_args)


def print_check(message, if_yes='found', if_no='not found'):
    """Decorator to print pre/post-check messages."""
    def sub_decorator(f):
        def sub_func(*args, **kwargs):
            sys.stderr.write(f'-- {message}\n')
            result = f(*args, **kwargs)
            result_output = if_yes if result else if_no
            sys.stderr.write(f'-- {message} -- {result_output}\n')
            return result
        sub_func.pkgdist_config_decorated = True
        return sub_func
    return sub_decorator


def cache_check(cache_key):
    """Method decorate to cache check result."""
    def sub_decorator(f):
        def sub_func(self, *args, **kwargs):
            if cache_key in self.cache:
                return self.cache[cache_key]
            result = f(self, *args, **kwargs)
            self.cache[cache_key] = result
            return result
        sub_func.pkgdist_config_decorated = True
        return sub_func
    return sub_decorator


def check_define(define_name):
    """Method decorator to store check result."""
    def sub_decorator(f):
        @cache_check(define_name)
        def sub_func(self, *args, **kwargs):
            result = f(self, *args, **kwargs)
            self.check_defines[define_name] = result
            return result
        sub_func.pkgdist_config_decorated = True
        return sub_func
    return sub_decorator


class config(dst_config.config):
    """Perform platform checks for extension build."""

    user_options = dst_config.config.user_options + [
        ("cache-path", "C", "path to read/write configuration cache"),
    ]

    def initialize_options(self):
        self.cache_path = None
        self.build_base = None
        dst_config.config.initialize_options(self)

    def finalize_options(self):
        if self.cache_path is None:
            self.set_undefined_options(
                'build',
                ('build_base', 'build_base'))
            self.cache_path = os.path.join(self.build_base, 'config.cache')
        dst_config.config.finalize_options(self)

    def _cache_env_key(self):
        return (self.cc, self.include_dirs, self.libraries, self.library_dirs)

    @cache_check('_sanity_check')
    @print_check('Performing basic C toolchain sanity check', 'works', 'broken')
    def _sanity_check(self):
        return self.try_link("int main(int argc, char *argv[]) { return 0; }")

    def run(self):
        with syspath(PACKAGEDIR, MODULE_NAME == 'snakeoil'):
            from snakeoil.pickling import dump, load

        # try to load the cached results
        try:
            with open(self.cache_path, 'rb') as f:
                cache_db = load(f)
        except (OSError, IOError):
            cache_db = {}
        else:
            if self._cache_env_key() == cache_db.get('env_key'):
                sys.stderr.write(f'-- Using cache: {self.cache_path}\n')
            else:
                sys.stderr.write('-- Build environment changed, discarding cache\n')
                cache_db = {}

        self.cache = cache_db.get('cache', {})
        self.check_defines = {}

        if not self._sanity_check():
            sys.stderr.write('The C toolchain is unable to compile & link a simple C program!\n')
            sys.exit(1)

        # run all decorated methods
        for k in dir(self):
            if k.startswith('_'):
                continue
            if hasattr(getattr(self, k), 'pkgdist_config_decorated'):
                getattr(self, k)()

        # store results in Distribution instance
        self.distribution.check_defines = self.check_defines
        # store updated cache
        cache_db = {
            'cache': self.cache,
            'env_key': self._cache_env_key(),
        }
        self.mkpath(os.path.dirname(self.cache_path))
        with open(self.cache_path, 'wb') as f:
            dump(cache_db, f)

    # == methods for custom checks ==
    def check_struct_member(self, typename, member, headers=None, include_dirs=None, lang="c"):
        """Check whether typename (must be struct or union) has the named member."""
        return self.try_compile(
            'int main() { %s x; (void) x.%s; return 0; }'
            % (typename, member), headers, include_dirs, lang)


# directly copied from snakeoil.contexts
@contextmanager
def syspath(path, condition=True, position=0):
    """Context manager that mangles sys.path and then reverts on exit.

    Args:
        path: The directory path to add to sys.path.
        condition: Optional boolean that decides whether sys.path is mangled or
            not, defaults to being enabled.
        position: Optional integer that is the place where the path is inserted
            in sys.path, defaults to prepending.
    """
    syspath = sys.path[:]
    if condition:
        sys.path.insert(position, path)
    try:
        yield
    finally:
        sys.path = syspath


# directly copied from snakeoil.version
# currently required to avoid test failures when running directly via the setup script
def get_git_version(path):
    """Return git related revision data."""
    path = os.path.abspath(path)
    try:
        stdout, ret = _run_git(path, ["log", "--format=%H\n%aD", "HEAD^..HEAD"])

        if ret != 0:
            return None

        data = stdout.decode().splitlines()
        tag = _get_git_tag(path, data[0])

        # get number of commits since most recent tag
        stdout, ret = _run_git(path, ['describe', '--tags', '--abbrev=0'])
        prev_tag = None
        commits = None
        if ret == 0:
            prev_tag = stdout.decode().strip()
            stdout, ret = _run_git(
                path, ['log', '--oneline', f'{prev_tag}..HEAD'])
            if ret == 0:
                commits = len(stdout.decode().splitlines())

        return {
            'rev': data[0],
            'date': data[1],
            'tag': tag,
            'commits': commits,
        }
    except EnvironmentError as e:
        # ENOENT is thrown when the git binary can't be found.
        if e.errno != errno.ENOENT:
            raise
        return None


def _run_git(path, cmd):
    env = dict(os.environ)
    env["LC_CTYPE"] = "C"

    r = subprocess.Popen(
        ['git'] + list(cmd), stdout=subprocess.PIPE, env=env,
        stderr=subprocess.DEVNULL, cwd=path)

    stdout = r.communicate()[0]
    return stdout, r.returncode


def _get_git_tag(path, rev):
    stdout, _ = _run_git(path, ['name-rev', '--tag', rev])
    tag = stdout.decode().split()
    if len(tag) != 2:
        return None
    tag = tag[1]
    if not tag.startswith("tags/"):
        return None
    tag = tag[len("tags/"):]
    if tag.endswith("^0"):
        tag = tag[:-2]
    if tag.startswith("v"):
        tag = tag[1:]
    return tag


@contextmanager
def suppress(verbosity=0):
    """Context manager that conditionally suppresses stdout/stderr."""
    with ExitStack() as stack:
        with open(os.devnull, 'w') as null:
            if verbosity < 0:
                stack.enter_context(redirect_stdout(null))
            if verbosity < 1:
                stack.enter_context(redirect_stderr(null))
            yield
