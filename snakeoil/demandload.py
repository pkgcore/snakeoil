# Copyright: 2007 Marien Zwart <marienz@gentoo.org>: GPL2/BSD
# Copyright: 2009-2011 Brian Harring <ferringb@gmail.com>: GPL2/BSD
# License: GPL2

"""Demand load things when used.

This uses :py:func:`Placeholder` objects which create an actual object on
first use and know how to replace themselves with that object, so
there is no performance penalty after first use.

This trick is *mostly* transparent, but there are a few things you
have to be careful with:

 - You may not bind a second name to a placeholder object. Specifically,
   if you demandload C{bar} in module C{foo}, you may not
   C{from foo import bar} in a third module. The placeholder object
   does not "know" it gets imported, so this does not trigger the
   demandload: C{bar} in the third module is the placeholder object.
   When that placeholder gets used it replaces itself with the actual
   module in C{foo} but not in the third module.
   Because this is normally unwanted (it introduces a small
   performance hit) the placeholder object will raise an exception if
   it detects this. But if the demandload gets triggered before the
   third module is imported you do not get that exception, so you
   have to be careful not to import or otherwise pass around the
   placeholder object without triggering it.
 - Not all operations on the placeholder object trigger demandload.
   The most common problem is that C{except ExceptionClass} does not
   work if C{ExceptionClass} is a placeholder.
   C{except module.ExceptionClass} with C{module} a placeholder does
   work. You can normally avoid this by always demandloading the
   module, not something in it.
"""

__all__ = ("demandload", "demand_compile_regexp")

# TODO: the use of a curried func instead of subclassing needs more thought.

# the replace_func used by Placeholder is currently passed in as an
# external callable, with "partial" used to provide arguments to it.
# This works, but has the disadvantage that calling
# demand_compile_regexp needs to import re (to hand re.compile to
# partial). One way to avoid that would be to add a wrapper function
# that delays the import (well, triggers the demandload) at the time
# the regexp is used, but that's a bit convoluted. A different way is
# to make replace_func a method of Placeholder implemented through
# subclassing instead of a callable passed to its __init__. The
# current version does not do this because getting/setting attributes
# of Placeholder is annoying because of the
# __getattribute__/__setattr__ override.


import os
import sys
from snakeoil.modules import load_any
from snakeoil.currying import partial
from snakeoil import compatibility

# There are some demandloaded imports below the definition of demandload.

_allowed_chars = "".join((x.isalnum() or x in "_.") and " " or "a"
    for x in map(chr, xrange(256)))

py3k_translate = {
    "itertools": dict(("i%s" % k, k) for k in
        ("filterfalse",)),
    "ConfigParser": "configparser",
    "Queue":"queue",
    "StringIO":"io",
    "cStringIO":"io",
}

def parse_imports(imports):
    """Parse a sequence of strings describing imports.

    For every input string it returns a tuple of (import, targetname).
    Examples::

      'foo' -> ('foo', 'foo')
      'foo:bar' -> ('foo.bar', 'bar')
      'foo:bar,baz@spork' -> ('foo.bar', 'bar'), ('foo.baz', 'spork')
      'foo@bar' -> ('foo', 'bar')

    Notice 'foo.bar' is not a valid input. This simplifies the code,
    but if it is desired it can be added back.

    :type imports: sequence of C{str} objects.
    :rtype: iterable of tuples of two C{str} objects.
    """
    for s in imports:
        fromlist = s.split(':', 1)
        if len(fromlist) == 1:
            # Not a "from" import.
            if '.' in s:
                raise ValueError('dotted imports unsupported; %r' % s)
            split = s.split('@', 1)
            for s in split:
                if not s.translate(_allowed_chars).isspace():
                    raise ValueError("bad target: %s" % s)
            if len(split) == 2:
                yield tuple(split)
            else:
                split = split[0]
                if compatibility.is_py3k:
                    if isinstance(py3k_translate.get(split, None), str):
                        yield py3k_translate[split], split
                    else:
                        yield split, split
                else:
                    yield split, split
        else:
            # "from" import.
            base, targets = fromlist
            if not base.translate(_allowed_chars).isspace():
                raise ValueError("bad target: %s" % base)
            if compatibility.is_py3k:
                if isinstance(py3k_translate.get(base, None), str):
                    base = py3k_translate[base]
            for target in targets.split(','):
                split = target.split('@', 1)
                for s in split:
                    if not s.translate(_allowed_chars).isspace():
                        raise ValueError("bad target: %s" % s)
                if compatibility.is_py3k:
                    split[0] = py3k_translate.get(base, {}).get(split[0], split[0])
                yield base + '.' + split[0], split[-1]
def _protection_enabled_disabled():
    return False

def _noisy_protection_disabled():
    return False

def _protection_enabled_enabled():
    val = os.environ.get("SNAKEOIL_DEMANDLOAD_PROTECTION", "n").lower()
    return val in ("yes", "true", "1", "y")

def _noisy_protection_enabled():
    val = os.environ.get("SNAKEOIL_DEMANDLOAD_WARN", "y").lower()
    return val in ("yes", "true", "1", "y")

if 'pydoc' in sys.modules or 'epydoc' in sys.modules:
    _protection_enabled = _protection_enabled_disabled
    _noisy_protection = _noisy_protection_disabled
else:
    _protection_enabled = _protection_enabled_enabled
    _noisy_protection = _noisy_protection_enabled


class Placeholder(object):

    """Object that knows how to replace itself when first accessed.

    See the module docstring for common problems with its use.
    """

    def __init__(self, scope, name, replace_func):
        """Initialize.

        :param scope: the scope we live in, normally the result of
          C{globals()}.
        :param name: the name we have in C{scope}.
        :param replace_func: callable returning the object to replace us with.
        """
        object.__setattr__(self, '_scope', scope)
        object.__setattr__(self, '_name', name)
        object.__setattr__(self, '_replace_func', replace_func)
        object.__setattr__(self, '_replacing_tids', [])

    def _already_replaced(self):
        name = object.__getattribute__(self, '_name')
        scope = object.__getattribute__(self, '_scope')

        # in a threaded environment, it's possible for tid1 to get the
        # placeholder from globals, python switches to tid2, which triggers
        # a full update (thus enabling this pathway), switch back to tid1,
        # which then throws the complaint.
        # this cannot be locked to address; the pull from global scope is
        # what would need locking, and that's infeasible (VM shouldn't do it
        # anyways; would kill performance)
        # if threading is enabled, we'll have the tid's of the threads that
        # triggered replacement; if the thread triggering this pathway isn't
        # one of the ones that caused replacement, silence the warning.
        # as for why we watch for the threading modules; if they're not there,
        # it's impossible for this pathway to accidentally be triggered twice-
        # meaning it is a misuse by the consuming client code.
        if 'threading' in sys.modules or 'thread' in sys.modules:
            tids_to_complain_about = object.__getattribute__(self, '_replacing_tids')
            complain = _get_thread_ident() in tids_to_complain_about
        else:
            complain = True

        if complain:
            if _protection_enabled():
                raise ValueError('Placeholder for %r was triggered twice' % (name,))
            elif _noisy_protection():
                logging.warning('Placeholder for %r was triggered multiple times '
                    'in file %r' % (name, scope.get("__file__", "unknown")))
        return scope[name]

    def _replace(self):
        """Replace ourself in C{scope} with the result of our C{replace_func}.

        @returns: the result of calling C{replace_func}.
        """
        replace_func = object.__getattribute__(self, '_replace_func')
        scope = object.__getattribute__(self, '_scope')
        name = object.__getattribute__(self, '_name')

        result = replace_func()
        scope[name] = result

        # Paranoia, explained in the module docstring.
        # note that this *must* follow scope mutation, else it can cause
        # issues for threading
        already_replaced = object.__getattribute__(self, '_already_replaced')
        object.__setattr__(self, '_replace_func', already_replaced)

        # note this step *has* to follow scope modification; else it
        # will go maximum depth recursion.
        if 'thread' in sys.modules or 'threading' in sys.modules:
            tids = object.__getattribute__(self, '_replacing_tids')
            tids.append(_get_thread_ident())

        return result

    # Various methods proxied to our replacement.

    def __str__(self):
        return self.__getattribute__('__str__')()

    def __getattribute__(self, attr):
        result = object.__getattribute__(self, '_replace')()
        return getattr(result, attr)

    def __setattr__(self, attr, value):
        result = object.__getattribute__(self, '_replace')()
        setattr(result, attr, value)

    def __call__(self, *args, **kwargs):
        result = object.__getattribute__(self, '_replace')()
        return result(*args, **kwargs)


def demandload(scope, *imports):
    """Import modules into scope when each is first used.

    scope should be the value of C{globals()} in the module calling
    this function. (using C{locals()} may work but is not recommended
    since mutating that is not safe).

    Other args are strings listing module names.
    names are handled like this::

      foo            import foo
      foo@bar        import foo as bar
      foo:bar        from foo import bar
      foo:bar,quux   from foo import bar, quux
      foo.bar:quux   from foo.bar import quux
      foo:baz@quux   from foo import baz as quux
    """
    for source, target in parse_imports(imports):
        scope[target] = Placeholder(scope, target, partial(load_any, source))


# Extra name to make undoing monkeypatching demandload with
# disabled_demandload easier.
enabled_demandload = demandload


def disabled_demandload(scope, *imports):
    """Exactly like :py:func:`demandload` but does all imports immediately."""
    for source, target in parse_imports(imports):
        scope[target] = load_any(source)


class RegexPlaceholder(Placeholder):
    """
    Compiled Regex object that knows how to replace itself when first accessed.

    See the module docstring for common problems with its use; used by
    :py:func:`demand_compile_regexp`.
    """

    def _replace(self):
        args, kwargs = object.__getattribute__(self, '_replace_func')
        object.__setattr__(self, '_replace_func',
            partial(re.compile, *args, **kwargs))
        return Placeholder._replace(self)



def demand_compile_regexp(scope, name, *args, **kwargs):
    """Demandloaded version of :py:func:`re.compile`.

    Extra arguments are passed unchanged to :py:func:`re.compile`.

    This returns the placeholder, which you *must* bind to C{name} in
    the scope you pass as C{scope}. It is done this way to prevent
    confusing code analysis tools like pylint.

    :param scope: the scope, just like for :py:func:`demandload`.
    :param name: the name of the compiled re object in that scope.
    :returns: for compatibility, the placeholder object.  It's deprecated to
        rely on this however.
    """
    r = scope[name] = RegexPlaceholder(scope, name, (args, kwargs))
    return r


def disabled_demand_compile_regexp(scope, name, *args, **kwargs):
    """Exactly like :py:func:`demand_compile_regexp` but does all imports immediately."""
    scope[name] = re.compile(*args, **kwargs)


if os.environ.get("SNAKEOIL_DEMANDLOAD_DISABLED", 'n').lower() in ('y', 'yes' '1', 'true'):
    demandload = disabled_demandload
    demand_compile_regexp = disabled_demand_compile_regexp

demandload(globals(), 're', 'logging')

if compatibility.is_py3k:
    demandload(globals(), 'threading')
    def _get_thread_ident():
        return threading.current_thread().ident
else:
    demandload(globals(), 'thread')
    def _get_thread_ident():
        return thread.get_ident()
