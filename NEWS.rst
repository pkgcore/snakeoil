=============
Release Notes
=============

snakeoil 0.7.1 (2016-10-30)
---------------------------

- Drop py3.3 support.

- snakeoil.process.namespaces: Ignore recursive remounting errors for the root
  directory. When layering namespaces only the first mount() call in this case
  will work, subsequent calls will raise invalid argument errors.

snakeoil 0.7.0 (2016-05-28)
---------------------------

- snakeoil.xml: Prefer lxml.etree when available.

- snakeoil.bash: Conditional line continuation support for iter_read_bash().

- snakeoil.dist.distutils_extensions: Move to external pkgdist project and
  bundle the standalone module to circumvent pre-setup parsing dep cycles.

- snakeoil.lists: Deprecated module name was renamed to snakeoil.sequences.
  Stub will exist with warnings until 0.8.

- snakeoil.osutils: Add supported_systems() decorator to support restricting
  functions to set of supported systems.

- snakeoil.process: Remove get_proc_count() and get_physical_proc_count().

- snakeoil.cli.arghparse: Add generic argparse related support from pkgcore.

snakeoil 0.6.6 (2015-12-13)
---------------------------

- snakeoil.cli: Add userquery() from pkgcore.ebuild.formatter.

- snakeoil.formatters: Don't force colored output if the terminal doesn't
  support it.

- Add support for adding extended docs to argparse arguments via the 'docs'
  kwarg. This allows for adding extended content meant for man pages directly
  to the arguments in scripts. To enable support, all that must be done is
  importing snakeoil.cli which will monkeypatch add_argument() from argparse to
  ignore 'docs' kwargs by default. The extended content can be pulled at
  certain times such as during doc generation by setting a flag, see
  snakeoil.dist.generate_man_rsts for example usage.

- snakeoil.dist.distutils_extensions: Drop get_number_of_processors() since
  multiprocessing.cpu_count is used instead.

- snakeoil.klass: Add patch decorator method for simplified monkeypatching.

- snakeoil.contextlib has been moved to snakeoil.contexts to avoid any potential
  namespace issues from contextlib in the stdlib.

snakeoil 0.6.5 (2015-08-10)
---------------------------

- snakeoil.process: Add is_running() that determines whether a process is
  running or not using the PID status from the proc filesystem.

- snakeoil.process: Deprecate get_physical_proc_count() and get_proc_count(),
  use cpu_count() from multiprocessing instead or other similar support.
  Support will be removed in 0.7.

- Add a build_py3 target to snakeoil.dist.distutils_extensions to allow for
  writing py3 compatible code and using 3to2 for conversion purposes instead of
  writing py2 compatible code and using 2to3 during project builds.

- Drop some extra complexity from snakeoil.osutils.ensure_dirs(), mostly this
  entails not altering perms on existing dirs anymore while traversing up the
  components of a given path.

- Add initial user namespace support functionality. Currently the process
  running the code gets its uid/gid mapped to root in the new namespace, but
  that will be made more configurable later on.

- Add support for setting the system hostname and domain name under a UTS
  namespace.

- Make sure child mount namespaces don't affect their parents. Some distros use
  shared rootfs mount namespaces by default so child mount namespace mount
  events propagate back up to their parents if they aren't made private or
  slaved.

- Move mount methods from snakeoil.osutils into their own module at
  snakeoil.osutils.mount.

- snakeoil.fileutils: add a touch(1) equivalent.

- Add the beginnings of a context manager module as snakeoil.contextlib.
  Currently this just includes the SplitExec class leveraged by pychroot.

- Move snakeoil.namespaces to snakeoil.process.namespaces since they directly
  relate to processes and we'll probably add a similar module for cgroups in
  the near future.

- snakeoil.version: format_version() was merged into get_version().

snakeoil 0.6.4 (2015-06-28)
---------------------------

- Add header install directory to the search path when building extensions.
  This helps fix building consumers like pkgcore in virtualenvs.

- Simplify snakeoil.xml by dropping deprecated elementtree related module
  fallbacks.

- Drop internal OrderedDict implementation from snakeoil.mappings, use the
  version from collections instead.

- Fix snakeoil.compatibility ConfigParser defaults so 3rd party usage doesn't
  get overridden.

- Add ctypes-based umount/umount2 wrapper in snakeoil.osutils.


snakeoil 0.6.3 (2015-04-01)
---------------------------

- Remove temporary plugincache generated during tests so it isn't installed.


snakeoil 0.6.2 (2015-04-01)
---------------------------

- Add locking for demandload replace operations during the scope modification
  phase, fixing threaded access.

- Fix fd leak during highly-threaded pmaint regen runs due to a cyclic
  reference issue in readlines_iter from snakeoil.fileutils.

- Fix py3k argument encoding for mount() from snakeoil.osutils.

- Add tox-based testsuite support.

- Drop distutils sdist filelist workaround and respect MANIFEST.in instead.


snakeoil 0.6.1 (2015-03-24)
---------------------------

- Add ProxiedAttrs mappings class used as a proxy mapping protocol to an
  object's attributes.

- Update namespace support and move it into snakeoil.namespaces.

- Add ctypes-based mount(2) wrapper in snakeoil.osutils.

- Deprecate snakeoil.modules.load_module, importlib.import_module should be
  used instead.

- Downgrade scope from a required argument to a optional keyword argument for
  demandload, the caller's global scope is used by default when no argument is
  passed.


snakeoil 0.6 (2014-12-01)
-------------------------

- Make sure shared memory has the right rwx permissions for multiprocessing
  semaphores.

- Fix race condition for demand compiled regexps which solves various threading
  issues including running a parallelized `pmaint regen` in pkgcore.

- Remove old compat snakeoil.fileutils imports from snakeoil.osutils and
  make_SlottedDict_kls from snakeoil.obj.

- Drop python2.4 any/all built-ins compat, python2.6 is_disjoint compat, and
  pre-python2.6 next built-in compat.

- Remove pre-python2.7 compat support including iterables.chain_from_iterables
  (use chain.from_iterable from itertools), is_disjoint (use
  isdisjoint), and built-in backports for all, any, and next.

- Drop deprecated currying.alias_class_method; use klass.alias_method.

- Migrate pkgcore.vdb.ondisk.bz2_data_source to
  snakeoil.data_source.bz2_source.

- Drop deprecated getters from snakeoil.data_source; attrs and functions
  should be accessed directly.

- Move snakeoil.fileutils.read_dict to snakeoil.bash.read_dict and drop
  compatibility shims for the iter_read_bash and read_bash_dict methods from
  fileutils.

- Add support to klass.steal_docs to clone docstrings from regular functions in
  addition to class functions.


snakeoil 0.5.3 (2013-09-26)
---------------------------

- Simplify sphinx-build handling, removing checks for Gentoo specific suffixes.

- Switch from pbzip2 to lbzip2 for parallel bzip2 support since lbzip2 can
  handle parallel decompression of regular non-lbzip2 compressed files unlike
  pbzip2.

- Fix python3.3 support.


snakeoil 0.5.2 (2012-10-17)
---------------------------

- Fixed doc generation for py3k, including threading appropriate python
  path/version down through the generation.


snakeoil 0.5.1 (2012-09-29)
----------------------------

- Fix corner case exception in formatter extension, cleanup potential
  NULL derefs.

- If hashlib has a whirlpool implementation, we use it and prefer it
  over mhash or our fallback implementation; it's faster, drops the
  GIL, and generally is the bees-knees.

- compatibility.raise_from no longer looses traceback information in
  >py3k.


snakeoil 0.5 (2012-08-04)
-------------------------

- lintplugins were updated to pylint 0.25.1 API; likely works with >=0.21.

- Added awareness of PEP3149 naming schemes to the namespace walkers.

- Fixed utime related race in 2to3 cacher; comes about due to python not
  stamping the inode w/ the exact float given, represents via a particular
  source file being converted a second time (typically breaking it); only
  triggerable in local development, however it's annoying, thus sorted.

- Effective immediately, python2.4 is no longer supported.  Last release
  was in '08, so really, really don't care anymore.

- snakeoil.chksum grew whirlpool support, including native python fallback.

- snakeoil.chksum grew sha512 support.

- snakeoil.sphinx_utils was added w/ two reusable/importable scripts;

  - generate_api_rsts.py: scans a given python namespace, generating properly
    structured ReST docs.  This is intended for better api doc generation than
    what sphinx's autodoc tools currently provide.

  - generate_news_rst.py: given a mostly ReST like NEWS/changelog file, this
    can convert into into pages like
    http://docs.snakeoil.googlecode.com/git/news.html .  Given appropriate
    args, it can bind in release urls, git shortlog urls, and generally make
    it fairly pretty while useful.

- snakeoil.version is now reusable for other projects, and the _verinfo format
  it uses has been converted to storing a dictionary (better deserialization
  namely via having it as a dict).

- snakeoil.distutils_extensions:

  - sphinx_build_doc now always returns
    a class for usage, rather than None if sphinx wasn't available.  Clients
    should use this, and structure their deps appropriately to not execute
    doc building unless desired (in which case it's better to have the command
    throw an error, instead of having distutils state "no such command" for
    a build_doc target for example).

  - build and install now support generating _verinfo files automatically
    from git, and installing them if the support is enabled.

  - All bzr related code has been ripped out in full.

- Docstring work, and general doc's overhaul (including site updates).

- snakeoil.process now exposes functionality for finding the number of
  actual HW cores, filtering out HT cpus.  This is relevant since certain
  operations (pbzip2 in particular) aren't any faster using HT- they just
  consume more cpu.

- Api's have been shifting a bit; compatibility was left in place, but
  large chunks of snakeoil.osutils and snakeoil.fileutils have moved to
  the appropriate place.

- Compression framework was added; snakeoil.compression.  Has built in
  awareness of pbzip2, parallelization, and will use the most efficient
  form it can to get things done (primarily threaded, but implemented
  in a fashion where the GIL doesn't matter thus can easily hit multi
  core).

- closerange compatibility method was added for <2.6; this method of
  closing is far faster than normal "scan all fds", thus exposing it.


snakeoil 0.4.6 (2011-12-14)
---------------------------

- for bash parsing, pass into shlex the file being read so that
  relative source calls can find the file correctly.  Issue #1.

- add currying.wrap_exception and currying.wrap_exception_complex


snakeoil 0.4.5 (2011-11-30)
---------------------------

- Fix defaultdict in py2.4 to be compatible with >=py2.5 defaultdict.

- Fix WeakRefFinalizer so that instances that are still strongly referenced
  at the time of sys.exit have their finalizers ran via atexit; specifically,
  run the finalizers only for that pid.


snakeoil 0.4.4 (2011-10-26)
---------------------------

- use sane permissions for directories created for tests.

- swallow ENOTDIR from readfiles and readlines if told to ignore
  missing files.


snakeoil 0.4.3 (2011-09-27)
---------------------------

- snakeoil.demandload is now threading aware, and no longer will complain
  if threading leads to an accidental already-replaced placeholder access.

- snakeoil.osutils.read* moved to snakeoil.fileutils; compatibility
  shim will be removed in 0.5.

- fileutils.write_file was added for quick one off writes.

- chksums generation now will parallelize where worthwhile.  Since this is
  python, GIL bouncing does occur, ultimately costing more total CPU for the
  larger/more chksums.  That said, it's overall faster going in parallel
  (for 4 chksummers, it's about 75% faster; for 2, about 40% faster).

  Again, note this is enabled by default.  To disable, parallelize=False.

- added snakeoil.process for getting processor count

- don't install compatibility_py3k.py if we're targetting py2k; no need,
  and it pisses off pyc generation.


snakeoil 0.4.2 (2011-09-02)
---------------------------

- compatibility.raise_from; compatibility across py2k/py3k for doing py3k
  raise EXCEPTION from CAUSE; see pep3134.  Primarily for raising an exception
  which was caused by another (casting an exception essentially).

- added klass.cached_property, and fixed klass.jit_attr to block bad usage
  that goes recursive.

- add distutils_extension for building sphinx docs

- if the invoking python has issue 7604 fixed, then use a fast single lookup
  version of delitem for slotted instances; else use the normal double lookup
  workaround.


snakeoil 0.4.1 (2011-06-22)
---------------------------

- issue 7567; python2.7.1 reintroduces it (2.7 lacked it).  Gentoo bug 350215.

- snakeoil.unittest_extensions was split out from distutils_extensions.

- snakeoil.obj.make_SlottedDict_kls moved to mappings; it'll be removed from
  snakeoil.obj in 0.5.

- currying.alias_class_method is now deprecated; use klass.alias_method
  instead.

- handle differing lib2to3 dependant on multiprocessing existance.


snakeoil 0.4 (2011-04-24)
-------------------------

- added snakeoil.klass.immutable_instance metaclass and an equivalent inject
  function for modifying the scope.  These are used to avoid classes adhoc'ing
  the same sort of functionality, rarely throwing appropriate/standardized
  exceptions.

- for any consumers of snakeoil's common header, for py2.4/py2.5 we've added
  suppression of the segfault potential for Py_CLEAR(tmp); see
  http://mail.python.org/pipermail/python-bugs-list/2008-July/055285.html
  for the sordid details.

- mappings.inject_getitem_as_getattr, and AttrAccessible were added.  The
  former is for modifying a class so that attribute access is proxied to
  item access (including rewriting KeyError to AttributeError); the latter
  is a general usable class for this.

- mappings.ListBackedDict and mappings.TupleBackedDict have been removed.

- demandload.demand_compile_regexp no longer returns the placeholder- instead
  it injects the placeholder directly into the scope, just like demandload
  does.

- added snakeoil.iterables.chain_from_iterable; this is compatibility for
  py2.4/py2.5, in >=py2.6 it just uses itertools.chain.from.iterable .

- initial work towards jython2.5 support.

- Massive amount of docstring work.  Yes, snakeoil is now documented and has
  examples.

- correct an off by one in caching_iter.

- snakeoil.dependant_methods.ForcedDepends grew two new methods;
  __set_stage_state__ for tweaking stage state manually, and
  __stage_step_callback__ for being notified on each stage completed.

- snakeoil.stringio; basically a py2k/py3k compatible set of class wrapping
  cStringIO/StringIO as necessary to provide readonly or writable versions of
  text vs bytes StringIO handles.  Note that readonly instances throw
  TypeError on write/truncate/etc, instead of cStringIO's behaviour or
  just not having the methods (or silently modifying things).

- pkgcore ticket 172; posix access technically allows for a root invoker to
  get a True result when doing X_OK on a non-executable file; this renders the
  function a fair bit useless for doing $PATH lookups for example, so we bundle
  a native python implementation that is fallen back to for userlands
  (opensolaris for example) that choose to implement that broken posix option.
  Linux/\*BSDs don't have this issue, so os.access is used for those userlands.

- pkgcore ticket 13; data_source.get* functions return handles that have
  .exceptions holding the exceptions they can throw, and that are caused by
  underlying implementation issues (versus caused by bad usage of the object).

- snakeoil data_source's will loose their get\_ methods in the next major
  version- they're kept strictly for compatibility.

- fix_copy.inject_copy will be removed after the next major version.  What
  remains does nothing.

- pkgcore.chksum was moved to snakeoil.chksum; pkgcore.interfaces.data_source
  was moved to snakeoil.data_source in addition.

- all bash functionality was split out of .fileutils into .bash

- osutils.readlines arg strip_newlines became strip_whitespace; if set,
  it'll wipe all leading/trailing whitespace from a line.

- snakeoil.weakrefs grew a new experimental metaclass; WeakRefFinalizer.
  Basically this class allows __del__ without the GC issues __del__ normally
  suffers.  Experimental, but should work- just keep in mind you get proxies
  back from users of that class.

- snakeoil.test.test_del_usage was added to scan for classes using __del__
  when they could use WeakRefFinalizer instead.

- snakeoil.lists.predicate_split; given a predicate function, a stream, and
  an optional key function (think DSU pattern for sorted), split the stream
  into two sequences- one sequence where the predicate evalutes true, the
  other sequence where it evaluates false.


- detect python bug 3770 (gentoo bug 330511), and disable multiprocessing
  for 2to3 conversion if it's found.


snakeoil 0.3.7 (2010-06-26)
---------------------------

- detect python bug 4660, and disable parallelization in 2to3 conversion if
  the system suffers from it.  This fixes an occasional "task_not_done"
  ValueError.

- minor optimization to TerminfoFormatters to cache and reuse TerminfoColor.
  Exempting the formatter, Terminfo* objects are now immutable

- snakeoil.mappings.defaultdict; compatibility implementation, defaults to
  collections.defaultdict for >=python-2.5, a native python implementation
  for 2.4



snakeoil 0.3.6.5 (2010-05-21)
-----------------------------

- add discard method to AtomicWriteFile to intentionally discard the
  updated content.

- fix initialization of RefCountingSet to set the refcount correctly on
  duplicate keys


snakeoil 0.3.6.4 (2010-04-21)
-----------------------------

- fix rare segfault potential with cpython generic_equality __eq__/__ne__
  when it's blindly transferred across classes.

- fix py3k handling of terminfo entries- xterm for example was affected.


snakeoil 0.3.6.3 (2010-03-14)
-----------------------------

- 'dumb' terminfo is no longer tempted- to useless to hack around it.

- get_formatters now properly falls back to plain text formatting if no
  terminfo could be found.


snakeoil 0.3.6.2 (2010-02-15)
-----------------------------

- overhauls to 2to3k support; speedup caching by near 16% via moving it into
  the process rather then as an external invocation.  Additionally fork the
  workers off to # of cpus on the system for parallelization when the results
  aren't cached.

- force -fno-strict-aliasing to be appended when it's invalidly left out by
  distutils internals.  See issue 969718 in pythons tracker.
  If you're using a non gcc compiler, you'll need to pass
  --disable-distutils-flag-fixing to disable the -fno-strict-aliasing
  additions.


snakeoil 0.3.6.1 (2010-02-07)
-----------------------------

- Licensing changes- see COPYING for specifics.  Majority of snakeoil
  is now GPL2/BSD 3 clause w/ a few exemptions.

- minor cleanup to extensions for GC support and stricter gcc.


snakeoil 0.3.6 (2010-01-08)
---------------------------

- add a cpy extension for jit_attr functionality; this brings the
  overhead down to effectively background noise for most usages.

- add a reflective_hash class to snakeoil.klass; this is primarily used
  for when the has is precomputed and stored somewhere.

- add an extension for ProtectedSet.__contains__; this levels a nice
  speedup for pcheck scans.

- enable a set of extensions for slots backed mappings; primarily affects
  pkgcore cache data objects, end result being pquery against a full
  repo in raw mode is about 8% faster overall.


snakeoil 0.3.5 (2009-12-27)
---------------------------

- snakeoil.struct_compat module was added; provides py2.4 compat, and
  adds read/write methods that take an fd and operate as unpack/pack
  against that fd.  This simplifies invocation/stream access primarily.

- add test_slot_shadowing; basically looks for __slots__ usage where
  a derivative class adds slotting the parent already provides, thus
  leading to a very unfun set of bugs and wasted memory.

- fix test_demandload_usage to properly recurse...


snakeoil 0.3.4 (2009-12-13)
---------------------------

- add compatibility.is_py3k_like for marking if it's >=py2.7, or py3k


snakeoil 0.3.3 (2009-10-26)
---------------------------

- use the registration framework for epydoc to make it aware of partials.

- monkeypatch pydoc.isdata on the fly to be aware of partials.  This
  makes pydoc output far more useful (and matches what is expected).

- experimental py3.1 support via 2to3.  setup.py automatically will
  convert the source if invoked by a py3k interpretter.

- snakeoil.osutils.readlines was expanded out into multiple functions,
  utf8, ascii, utf8_strict, ascii_strict, and bytes.  'Strict' means
  that we always want it decoded.  Non strict is useful when the file
  has some utf8 in it you don't care about, and don't want to take
  the codecs.open performance hit under py2k.  Under py3k, it's always
  decoded (required due to py3k changes).

- snakeoil.osutils.readfile was expanded out into multiple functions,
  utf8, ascii, ascii_strict, and bytes.  Use the appropriate one- this
  will make py3k compliance far easier.

- optimization in snakeoil.osutils.readlines; for small files, it's
  roughly a 4-8% speedup, for larger files (over half a meg) growing
  past 25%.  This puts its performance at roughly 2x over the open
  equivalent for small files, and near 10-15% faster for larger files.

- snakeoil.klass grew new properties to ease common tasks;
  jit_attr (invoke the target func to get the value, cache the value,
  return that value till the cached value is wiped).
  alias_attr (when that attr is accessed, hand the attribute the alias
  targets).

- snakeoil.compatibility additions; next, cmp, file_cls, and is_py3k, next,
  intern, sort_cmp (to paper over sorted no longer accepting a cmp arg), and
  sort_cmp (to paper over list.sort no longer accepting a cmp arg).

- snakeoil.klass.cached_hash; decorator to automatically cache the results
  of the target function.  primarily intended for __hash__ implementations.

- snakeoil.klass.inject_richcmp_methods_from_cmp ; passed a class scope,
  it'll automatically add __le__, __lt__, __gt__, __eq__, etc, via invoking
  __cmp__ if the python version is py3k.

- snakeoil/caching_2to3.py, a caching form of 2to3 that relies on an
  env var 'PY2TO3_CACHEDIR' to determine where to store cached versions
  of converted source.  Algorithm behind the cache is md5 based- if the
  md5 of the targeted source exists in the cachedir, it reuses the results
  from the previous run instead of invoking 2to3.  Massive performance
  speed up from this- uncached, setup.py test is ~32s.  cached, ~1.9s.
  That said, this is experimental- bug reports welcome however.

- setup.py test has been heavily enhanced- now it does its testing
  against a standalone install of the source, should have zero
  side affects on the underlying source.

- paper over a bug in cElementTree where it fails to import fully, but
  doesn't raise ImportError.  This address upstream python bug 3475.

- snakeoil no longer installs a bundled copy of elementtree if the
  python version is 2.5 or higher (no need, python bundles its own).

- snakeoil.test.test_demandload_usage now supports blacklisting- this
  is primarily useful for blocking py3k specific modules from being checked
  under py2k, and vice versa.

- in test_demandload_usage helper functionality it's possible for
  a file to disappear under its feet- ignore it, lock files from
  trial can trigger this.  Note it via logging.warn, and continue.


snakeoil 0.3.2 (2009-03-24)
---------------------------

- handle a race condition in ensure_dirs where the directory is created
  underfoot (thus a non issue).

- massive memory reduction for snakeoil.tar monkey patching;
  via punting the unused .buf storage (512 byes per TarInfo).  Grand total,
  this is a 70% reduction of the memory used compared to vanilla TarInfo
  (50% less then snakeoil 0.3).

- tweak snakeoil.tar monkey patching to re-enable memory savings on python2.6

- correct python2.6 compatibility issues; __(sizeof|format|subclasshook)__
  awareness, and handle getattr throwing AttributeError in the infinite
  recursion getattr tests.

- for test_demandload_usage, output the exception that caused the demandload
  'touch' to fail.


snakeoil 0.3.1 (2008-11-07)
---------------------------

- pkgcore ticket 215; fixup corner case errors in normpath cpy.


snakeoil 0.3 (2008-08-28)
-------------------------

- refactor dependant_methods to stop creating strong cycles that the python
  vm seems unable to break.  Shift the func storage away from .raw_func to
  .sd_raw_func in addition.  Add in __(un|)wrap_stage_dependencies__ so that
  invocation of unwrap then wrap will make changes to stage_depends take
  affect.

- intern gname and uname for TarInfo objects via property trickery- again,
  purpose being less memory usage.

- AtomicFile now marks itself as initially finalized until it has a fd; this
  removes spurios complaints from __del__

- LimitedChangeSet got an additional kwarg; key_validator.  A function can
  be passed in via this to do validation of the desired key- either it throws
  an exception, or returns the key to use.


snakeoil 0.2 (2008-03-18)
-------------------------

- snakeoil.fileutils.iter_read_bash and friends grew an allow_inline_comment
  param to control stripping of inlined comments; defaults to True.

- bash parsing bug where "x=y" w/out a trailing newline wasn't returning the
  'y' value.

- x=-* (specifically unquoted) is a valid assignment, fixed.

- added SNAKEOIL_DEMANDLOAD_PROTECTION environment variable- if set to
  something other then 'yes', disables the placeholder checks.
  Main intention for this functionality is for when code is introspecting
  demandload consuming code (epydoc for example), and inadvertantly triggers
  the access multiple times.


snakeoil 0.1 (2007-11-11)
-------------------------

- Add a cpython version of snakeoil.formatters.


snakeoil 0.1-rc2 (2007-07-06)
-----------------------------

- Pulled in any/all cpy extensions if not available in current python version.

- Added several pylint checks for naughty things like bool(len(seq)), itering
  over dict.keys() and shadowing builtins.

- Misc doc improvements.

- Rewrite demandload with a new multiple arg style, and update the appropriate
  pylint checker.

- Fix title updating by flushing the formatter's stream.

- overhaul demandload test case for consuming code.

- Add snakeoil.containers.SetMixin to provide set methods for various
  objects.

- Remove snakeoil.const - unused.

- Improve test coverage in general.

- Add folding dicts.

- Move snakeoil.file to snakeoil.fileutils.

- Initial release, split out from pkgcore.util.*.
