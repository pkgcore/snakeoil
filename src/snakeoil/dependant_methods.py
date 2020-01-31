"""Metaclass to inject dependencies into method calls.

Roughly, if you have 3 methods- that must be ran in the order of start, transfer, finish,
this metaclass enables you to force it such that if *finish* is called first,
start, than transfer, finally finish will be invoked transparently.

Methods involved should all require just ``self``.

The main usage for this code is to enable long chains of steps to be broken
down into individual methods, and the consuming api not being required to
know the proper order of invocation for that api unless they want to.

Most consumers of this metaclass wind up making a ``finish`` method the final step-
via that, consuming api's only requirement is knowing that if they invoke ``finish``
all necessary steps will be ran in the correct order.

Example usage:

>>> from snakeoil.dependant_methods import ForcedDepends
>>> class foo(metaclass=ForcedDepends):
...   stage_depends = {"finish": ("do_step1", "do_step2"),
...     "do_step1":"start", "do_step2": "start"}
...
...   def finish(self):
...     print("finish invoked")
...     return True
...   def do_step1(self):
...     print("running step1")
...     return True
...   def do_step2(self):
...     print("running step2")
...     return True
...   def start(self):
...     print("starting")
...     return True
>>>
>>> obj = foo()
>>> result = obj.finish()
starting
running step1
running step2
finish invoked
>>> result = obj.finish()
>>> # note, no output since finish has already been ran.
"""

from .currying import pre_curry
from .sequences import iflatten_instance

__all__ = ("ForcedDepends",)


def _ensure_deps(cls_id, name, func, self, *a, **kw):
    ignore_deps = kw.pop("ignore_deps", False)
    if id(self.__class__) != cls_id:
        # child class calling parent, or something similar. for cls_id
        # don't fire the dependants, nor update state
        return func(self, *a, **kw)

    if ignore_deps:
        s = [name]
    else:
        s = _yield_deps(self, self.stage_depends, name)

    r = True
    if not hasattr(self, '_stage_state'):
        self._stage_state = set()
    for dep in s:
        if dep not in self._stage_state:
            r = getattr(self, dep).sd_raw_func(self, *a, **kw)
            if not r:
                return r
            self._stage_state.add(dep)
            self.__stage_step_callback__(dep)
    return r


def _yield_deps(inst, d, k):
    # While at first glance this looks like should use expandable_chain,
    # it shouldn't. --charlie
    if k not in d:
        yield k
        return
    s = [k, iflatten_instance(d.get(k, ()))]
    while s:
        if isinstance(s[-1], str):
            yield s.pop(-1)
            continue
        exhausted = True
        for x in s[-1]:
            v = d.get(x)
            if v:
                s.append(x)
                s.append(iflatten_instance(v))
                exhausted = False
                break
            yield x
        if exhausted:
            s.pop(-1)


def __wrap_stage_dependencies__(cls):
    stage_depends = cls.stage_depends
    # we use id instead of the cls itself to prevent strong ref issues.
    cls_id = id(cls)
    for x in set(x for x in iflatten_instance(iter(stage_depends.items())) if x):
        try:
            f = getattr(cls, x)
        except AttributeError:
            raise TypeError(
                "class %r stage_depends specifies %r, which doesn't exist" %
                (cls, x))
        f2 = pre_curry(_ensure_deps, cls_id, x, f)
        f2.sd_raw_func = f
        setattr(cls, x, f2)


def __unwrap_stage_dependencies__(cls):
    stage_depends = cls.stage_depends
    for x in set(x for x in iflatten_instance(iter(stage_depends.items())) if x):
        try:
            f = getattr(cls, x)
        except AttributeError:
            raise TypeError(
                "class %r stage_depends specifies %r, which doesn't exist" %
                (cls, x))
        setattr(cls, x, getattr(f, 'sd_raw_func', f))


def __set_stage_state__(self, state):
    """set the completed stages to this sequence

    :param state: a sequence of stage names.  The names are not checked
      for validity- you can state that stage *x* has finished when there is no
      stage x.

      this should be used only when you know what you're doing
    """
    self._stage_state = set(state)


def __stage_step_callback__(self, stage):
    """callback invoked whenever a stage is completed with the completed stage name"""


class ForcedDepends(type):
    """
    Metaclass forcing methods to run in a certain order.

    Dependencies are controlled by the existance of a stage_depends
    dict in the class namespace. Its keys are method names, values are
    either a string (name of preceeding method), or list/tuple
    (proceeding methods).

    :cvar stage_depends: mapping of *stage* -> stages that must be ran first
        Dependant stages can either be a string (single stage), or a tuple- multiple stages,
        required in the order the're specified
    :cvar __stage_step_callback__: callback accepting a single arg, the phase that just ran.
        This method/callback is primarily useful for getting raw notification of stages that
        have just completed- whether for notifying a user, or for debugging.
    :cvar __set_stage_state__: method accepting a sequence; the stages completed for this
        instance are set to that sequence.  This should be used with extreme care; primarily
        useful for resuming a sequence of stages midway through.
    """

    def __new__(cls, name, bases, d):
        obj = super(ForcedDepends, cls).__new__(cls, name, bases, d)
        if not hasattr(obj, 'stage_depends'):
            obj.stage_depends = {}
        for x in ("wrap", "unwrap"):
            s = '__%s_stage_dependencies__' % x
            if not hasattr(obj, s):
                setattr(obj, s, classmethod(globals()[s]))

        obj.__unwrap_stage_dependencies__()
        obj.__wrap_stage_dependencies__()
        if not hasattr(obj, '__force_stage_state__'):
            obj.__set_stage_state__ = __set_stage_state__
        if not hasattr(obj, '__stage_step_callback__'):
            obj.__stage_step_callback__ = __stage_step_callback__
        return obj
