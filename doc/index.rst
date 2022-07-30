Welcome to snakeoil.  Now what is it?
=====================================

Snakeoil is a library with the rough intentions of holding common python
patterns/implementations, optimized common functionality, functionality to ease
supporting multiple python versions (specifically python2.5 through 3.3), and finally
well tested implementations of rather hard problems to solve.

Snakeoil's naming was chosen partially as a python analog of `liboil <http://liboil.freedesktop.org/>`_
(per cpu assembly optimizations of common operations), and also as a partial warning riffing
on the common meaning of `Snake Oil <http://en.wikipedia.org/wiki/Snake_oil>`_; specifically
a supposed miracle cure that has no effect.  To be clear, this package `does` have some
very powerful functionality and optimizations available, and its usage is well known to speed
things up: the `pkgcore <https://github.com/pkgcore/pkgcore>`_ package manager from which this
library was derived, makes heavy usage of these optimizations- further in a simple test usage
of :py:class:`snakeoil.caching.WeakInstMeta` to `portage <http://www.gentoo.org/proj/en/portage/>`_'s Atom class,
``emerge -ep system`` was sped up by 7% with a 20% memory reduction- specifically via just adding
that metaclass to their Atom class, a one line change.

The point the authors are trying to make however is that it is not a magic solve all.  Badly
performant code will still be badly performant code if it's due to algorithmic idiocies- swapping
in a snakeoil implementation for what affects 3% of your runtime won't do anything for the 97%
that is due to a bad quadratic algorithm for example.  Nor will using the more crazy
functionality we've got make your code necessarily any better to read- while snakeoil
endeavours to make its functionality simple, and to simplify consuming code, its usage
does not magically make horrible code better.

That said, a python mantra is "we're all adults here".  Snakeoil fully subscribes to this
philosophy- the warnings provided are merely to try and make it clear to people that snakeoil
while powerful, if used in a thoughtless fashion is not advisable.

Please note that snakeoil while relying on extensions in certain spots, does not require
the extensions to function- it will just fallback to native python implementations if it
cannot find its extensions to use.

Community
---------

Snakeoil now lives in full at |homepage|.  Issue tracking, wiki, groups, source, are all available from there.

Getting the source (downloading releases or trunk)
--------------------------------------------------

Snakeoil vcs of choice is `git <http://git.scm.org/>`_, and our source can be checked out at https://github.com/pkgcore/snakeoil

All releases are available at |release_url|\., with release news available at :ref:`releases`\.

As for dependencies, snakeoil basically just requires python3.8 and up.

Snakeoil intentions
===================

Following is a rough breakdown of the core areas snakeoil aims to cover.  This is not comprehensive-
generally speaking things that are useful have a way of winding up being added to snakeoil for reuse
elsewhere.

Python annoyances and hard issues
---------------------------------

The philosophy behind snakeoil is essentially that `things should just work`-
to that end, and via a fair amount of unit testing, snakeoil internals will cover up
the nasty details of how to do something while presenting a simple/no surprises api
for consumers.  Good examples of this are:

* :py:class:`snakeoil.caching.WeakInstMeta`, a metaclass allowing you to inline instance
  reuse for immutable objects.  Essentially, why write multiple factory implementations?  Why not
  push it directly into instance generation itself so that the instance sharing is transparent,
  not requiring the consumer to know that it's occuring?
* :py:func:`snakeoil.obj.DelayedInstantiation`; a object proxy implementation that is effectively
  fully transparent for any non-builtin target proxying it does.  While proxying implementations
  exist, the authors are aware of none that are reusable in this fashion, nor any that address the
  full issue of slotted methods (see the module for full details).

For the issues described above, these are not the simplest problems to solve- people typically
solve this on an adhoc basis, partially solving the issue but never fully addressing it.  The
purpose of snakeoil's functionality in that vein is to solve it once and for all, in one spot,
with the best possible implementation.  Let developers worry about their problem at hand, rather
than worry about solving an issue someone else has already addressed essentially.

Supporting multiple python versions can be a pain
-------------------------------------------------

Another facet of snakeoil functionality is python compatibility- :py:mod:`snakeoil.compatibility`
is a separate module that exists to address compatibility issues across py2.7 to py3.4- whether it
be intern moving to sys.intern, there is a significant amount of functionality in
there to help with these issues.  Note that compatibility functionality that goes into that module
isn't the only compatibility bits- that's just the general grab bag for it.
:py:mod:`snakeoil.currying` is another example (primarily targeting :py:class:`functools.partial`,
although providing more functionality than just that limited usage).

Optimizations
-------------

Snakeoil provides a fair amount of optimized implementations.  :py:mod:`snakeoil.osutils`
is a good spot to start for file operations/path manipulations, optimized sequence flattening (:py:class:`snakeoil.sequences.iflatten_instance`),
and optimized common patterns for class implementations (for example the :py:func:`snakeoil.klass.jit_attr` decorator which converts
secondary calls to the cached attribute into c level lookup speeds).  There is a fair bit more
than just those examples- it's in the readers interest to peruse our module docs, there is a fair amount
available.

For importation speed issues, we provide :py:mod:`snakeoil.demandload` - for anyone who has used bzrlib.lazy_import or
hg's equivalent implementation, this should be familiar.  In effect, it allows you to delay importation till
it's actually needed.  While it's not obvious, for well written scripts the time required for importation
can be come a large problem leaving people either the option of splitting up all functionality (which can
be very problematic from a codebase comprehension standpoint), or suffering the performance degradation.

As such, having a lazy importer is rather useful- your code still flows the same, just the import is
done only when something actually needs to access that functionality.

While we provide speed optimized implementations, we also provide functionality for reduction of memory
usage- for codebases with a large number of small dictionaries, :py:func:`snakeoil.mappings.make_SlottedDict_kls` can
reduce the memory requirement in the range of 75-95%.  For codebases that make extensive use of
``__slots__`` for memory reasons, it's advised that they take a look at :py:class:`snakeoil.test.test_slot_shadowing`

Avoiding Boilerplate (functionality to help with DRY- Don't Repeat Yourself)
----------------------------------------------------------------------------

Finally, for folks who have wrote a significantly large python codebase they wind up finding
themselves repeatedly writing the same type of functionality, over and over.  Things like __eq__
methods, attribute/class attribute aliasing for backwards compatibility, JIT properties, and
cloning documentation from preexisting sources.  If interested, :py:mod:`snakeoil.klass` is a
good place to start reading.

General Contents:
=================

.. toctree::
   :maxdepth: 2

   api/modules
   news

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
