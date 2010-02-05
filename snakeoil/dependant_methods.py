# Copyright: 2005-2008 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""Metaclass to inject dependencies into method calls.

Essentially, method a must be run prior to method b, invoking method a
if b is called first.
"""

from snakeoil.lists import iflatten_instance
from snakeoil.currying import pre_curry

__all__ = ["ForcedDepends"]

def ensure_deps(cls_id, name, func, self, *a, **kw):
    ignore_deps = kw.pop("ignore_deps", False)
    if id(self.__class__) != cls_id:
        # child class calling parent, or something similar. for cls_id
        # don't fire the dependants, nor update state
        return func(self, *a, **kw)

    if ignore_deps:
        s = [name]
    else:
        s = yield_deps(self, self.stage_depends, name)

    r = True
    if not hasattr(self, '_stage_state'):
        self._stage_state = set()
    for dep in s:
        if dep not in self._stage_state:
            r = getattr(self, dep).sd_raw_func(self, *a, **kw)
            if not r:
                return r
            self._stage_state.add(dep)
    return r


def yield_deps(inst, d, k):
    # While at first glance this looks like should use expandable_chain,
    # it shouldn't. --charlie
    if k not in d:
        yield k
        return
    s = [k, iflatten_instance(d.get(k, ()))]
    while s:
        if isinstance(s[-1], basestring):
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
    for x in set(x for x in iflatten_instance(stage_depends.iteritems()) if x):
        try:
            f = getattr(cls, x)
        except AttributeError:
            raise TypeError("class %r stage_depends specifies "
                "%r, which doesn't exist" % (cls, x))
        f2 = pre_curry(ensure_deps, cls_id, x, f)
        f2.sd_raw_func = f
        setattr(cls, x, f2)


def __unwrap_stage_dependencies__(cls):
    stage_depends = cls.stage_depends
    for x in set(x for x in iflatten_instance(stage_depends.iteritems()) if x):
        try:
            f = getattr(cls, x)
        except AttributeError:
            raise TypeError("class %r stage_depends specifies "
                "%r, which doesn't exist" % (cls, x))
        f2 = getattr(f, 'sd_raw_func', x)
        setattr(cls, x, getattr(f, 'sd_raw_func', f))


class ForcedDepends(type):
    """
    Metaclass forcing methods to run in a certain order.

    Dependencies are controlled by the existance of a stage_depends
    dict in the class namespace. Its keys are method names, values are
    either a string (name of preceeding method), or list/tuple
    (proceeding methods).

    U{pkgcore projects pkgcore.intefaces.format.build_base is an example consumer<http://pkgcore.org>}
    to look at for usage.
    """

    def __new__(cls, name, bases, d):
        obj = type.__new__(cls, name, bases,d)
        if not hasattr(obj, 'stage_depends'):
            obj.stage_depends = {}
        for x in ("wrap", "unwrap"):
            s = '__%s_stage_dependencies__' % x
            if not hasattr(obj, s):
                setattr(obj, s, classmethod(globals()[s]))

        obj.__unwrap_stage_dependencies__()
        obj.__wrap_stage_dependencies__()
        return obj
