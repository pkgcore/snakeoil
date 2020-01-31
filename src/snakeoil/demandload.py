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
 - You may not demandload more than one level of lookups.  Specifically,
   demandload("os.path") is not allowed- this would require a "os" fake
   object in the local scope, one which would have a "path" fake object
   pushed into the os object.  This is effectively not much of a limitation;
   you can instead just lazyload 'path' directly via demandload("os:path").
 - Not all operations on the placeholder object trigger demandload.
   The most common problem is that C{except ExceptionClass} does not
   work if C{ExceptionClass} is a placeholder.
   C{except module.ExceptionClass} with C{module} a placeholder does
   work. You can normally avoid this by always demandloading the module, not
   something in it. Another similar case is that C{isinstance Class} or
   C{issubclass Class} does not work for the initial call since the proper
   class hasn't replaced the placeholder until after the call. So the first
   call will always return False with subsequent calls working as expected. The
   previously mentioned workaround of demandloading the module works in this
   case as well.
"""

__all__ = ("demandload", "demand_compile_regexp")

import functools
import os
import sys
import threading

from .modules import load_any

# There are some demandloaded imports below the definition of demandload.

_allowed_chars = "".join((x.isalnum() or x in "_.") and " " or "a"
                         for x in map(chr, range(256)))


def parse_imports(imports):
    """Parse a sequence of strings describing imports.

    For every input string it returns a tuple of (import, targetname).
    Examples::

      'foo' -> ('foo', 'foo')
      'foo:bar' -> ('foo.bar', 'bar')
      'foo:bar,baz@spork' -> ('foo.bar', 'bar'), ('foo.baz', 'spork')
      'foo@bar' -> ('foo', 'bar')

    Notice 'foo.bar' is not a valid input.  Supporting 'foo.bar' would
    result in nested demandloaded objects- this isn't desirable for
    client code.  Instead use 'foo:bar'.

    :type imports: sequence of C{str} objects.
    :rtype: iterable of tuples of two C{str} objects.
    """
    for s in imports:
        fromlist = s.split(':', 1)
        if len(fromlist) == 1:
            # Not a "from" import.
            if '.' in s:
                raise ValueError(
                    "dotted imports are disallowed; see "
                    "snakeoil.demandload docstring for "
                    "details; %r" % s)
            split = s.split('@', 1)
            for s in split:
                if not s.translate(_allowed_chars).isspace():
                    raise ValueError("bad target: %s" % s)
            if len(split) == 2:
                yield tuple(split)
            else:
                split = split[0]
                yield split, split
        else:
            # "from" import.
            base, targets = fromlist
            if not base.translate(_allowed_chars).isspace():
                raise ValueError("bad target: %s" % base)
            for target in targets.split(','):
                split = target.split('@', 1)
                for s in split:
                    if not s.translate(_allowed_chars).isspace():
                        raise ValueError("bad target: %s" % s)
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


class Placeholder:

    """Object that knows how to replace itself when first accessed.

    See the module docstring for common problems with its use.
    """

    @classmethod
    def load_namespace(cls, scope, name, target):
        """Object that imports modules into scope when first used.

        See the module docstring for common problems with its use; used by
        :py:func:`demandload`.
        """
        if not isinstance(target, str):
            raise TypeError("Asked to load non string namespace: %r" % (target,))
        return cls(scope, name, functools.partial(load_any, target))

    @classmethod
    def load_regex(cls, scope, name, *args, **kwargs):
        """
        Compiled Regex object that knows how to replace itself when first accessed.

        See the module docstring for common problems with its use; used by
        :py:func:`demand_compile_regexp`.
        """
        if not args and not kwargs:
            raise TypeError("re.compile requires at least one arg or kwargs")
        return cls(scope, name, functools.partial(re.compile, *args, **kwargs))

    def __init__(self, scope, name, load_func):
        """Initialize.

        :param scope: the scope we live in, normally the global namespace of
            the caller (C{globals()}).
        :param name: the name we have in C{scope}.
        :param load_func: a functor that when invoked with no args, returns the
            object we're demandloading.
        """
        if not callable(load_func):
            raise TypeError("load_func must be callable; got %r" % (load_func,))
        object.__setattr__(self, '_scope', scope)
        object.__setattr__(self, '_name', name)
        object.__setattr__(self, '_replacing_tids', [])
        object.__setattr__(self, '_load_func', load_func)
        object.__setattr__(self, '_loading_lock', threading.Lock())

    def _target_already_loaded(self, complain=True):
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
        if complain:
            tids_to_complain_about = object.__getattribute__(self, '_replacing_tids')
            if threading.current_thread().ident in tids_to_complain_about:
                if _protection_enabled():
                    raise ValueError('Placeholder for %r was triggered twice' % (name,))
                elif _noisy_protection():
                    logging.warning('Placeholder for %r was triggered multiple times '
                                    'in file %r', name, scope.get("__file__", "unknown"))
        return scope[name]

    def _get_target(self):
        """Replace ourself in C{scope} with the result of our C{_load_func}.

        :return: the result of calling C{_load_func}.
        """
        preloaded_func = object.__getattribute__(self, '_target_already_loaded')
        with object.__getattribute__(self, '_loading_lock'):
            load_func = object.__getattribute__(self, '_load_func')
            if load_func is None:
                # This means that there was contention; two threads made it into
                # _get_target.  That's fine; suppress complaints, and return the
                # preloaded value.
                result = preloaded_func(False)
            else:
                # We're the first thread to try and do the load; load the target,
                # fix the scope, and replace this method with one that shortcircuits
                # (and appropriately complains) the lookup.
                result = load_func()
                scope = object.__getattribute__(self, '_scope')
                name = object.__getattribute__(self, '_name')
                scope[name] = result
                # Replace this method with the fast path/preloaded one; this
                # is to ensure complaints get leveled if needed.
                object.__setattr__(self, '_get_target', preloaded_func)
                object.__setattr__(self, '_load_func', None)


            # note this step *has* to follow scope modification; else it
            # will go maximum depth recursion.
            tids = object.__getattribute__(self, '_replacing_tids')
            tids.append(threading.current_thread().ident)

        return result

    def _load_func(self):
        raise NotImplementedError

    # Various methods proxied to our replacement.

    def __str__(self):
        return self.__getattribute__('__str__')()

    def __getattribute__(self, attr):
        result = object.__getattribute__(self, '_get_target')()
        return getattr(result, attr)

    def __setattr__(self, attr, value):
        result = object.__getattribute__(self, '_get_target')()
        setattr(result, attr, value)

    def __call__(self, *args, **kwargs):
        result = object.__getattribute__(self, '_get_target')()
        return result(*args, **kwargs)


def demandload(*imports, **kwargs):
    """Import modules into the caller's global namespace when each is first used.

    Other args are strings listing module names.
    names are handled like this::

    foo            import foo
    foo@bar        import foo as bar
    foo:bar        from foo import bar
    foo:bar,quux   from foo import bar, quux
    foo.bar:quux   from foo.bar import quux
    foo:baz@quux   from foo import baz as quux
    """

    # pull the caller's global namespace if undefined
    scope = kwargs.pop('scope', sys._getframe(1).f_globals)

    for source, target in parse_imports(imports):
        scope[target] = Placeholder.load_namespace(scope, target, source)


# Extra name to make undoing monkeypatching demandload with
# disabled_demandload easier.
enabled_demandload = demandload


def disabled_demandload(*imports, **kwargs):
    """Exactly like :py:func:`demandload` but does all imports immediately."""
    scope = kwargs.pop('scope', sys._getframe(1).f_globals)
    for source, target in parse_imports(imports):
        scope[target] = load_any(source)


def demand_compile_regexp(name, *args, **kwargs):
    """Demandloaded version of :py:func:`re.compile`.

    Extra arguments are passed unchanged to :py:func:`re.compile`.

    :param name: the name of the compiled re object in that scope.
    """
    scope = kwargs.pop('scope', sys._getframe(1).f_globals)
    scope[name] = Placeholder.load_regex(scope, name, *args, **kwargs)


def disabled_demand_compile_regexp(name, *args, **kwargs):
    """Exactly like :py:func:`demand_compile_regexp` but does all imports immediately."""
    scope = kwargs.pop('scope', sys._getframe(1).f_globals)
    scope[name] = re.compile(*args, **kwargs)


if os.environ.get("SNAKEOIL_DEMANDLOAD_DISABLED", 'n').lower() in ('y', 'yes' '1', 'true'):
    demandload = disabled_demandload
    demand_compile_regexp = disabled_demand_compile_regexp

demandload(
    'logging',
    're',
)
