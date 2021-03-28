import os
from functools import partial
from weakref import ref

from .obj import BaseDelayedObject


def finalize_instance(obj, weakref_inst):
    try:
        obj.__finalizer__()
    finally:
        obj.__disable_finalization__()


class WeakRefProxy(BaseDelayedObject):

    def __instantiate_proxy_instance__(self):
        obj = BaseDelayedObject.__instantiate_proxy_instance__(self)
        weakref = ref(self, partial(finalize_instance, obj))
        obj.__enable_finalization__(weakref)
        return obj


def __enable_finalization__(self, weakref):
    # note we directly access the class, to ensure the instance hasn't overshadowed.
    self.__class__.__finalizer_weakrefs__[os.getpid()][id(self)] = weakref


def __disable_finalization__(self):
    # note we directly access the class, to ensure the instance hasn't overshadowed.
    # use pop to allow for repeat invocations of __disable_finalization__
    d = self.__class__.__finalizer_weakrefs__.get(os.getpid)
    if d is not None:
        d.pop(id(self), None)
