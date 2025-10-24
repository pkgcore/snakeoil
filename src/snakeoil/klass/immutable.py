"""Implementations of immutable instance metaclasses"""

__all__ = ("immutable_instance", "inject_immutable_instance", "ImmutableInstance")


def _immutable_setattr(self, attr, value):
    raise AttributeError(self, attr)


def _immutable_delattr(self, attr):
    raise AttributeError(self, attr)


def immutable_instance(name, bases, scope, real_type=type):
    """metaclass that makes instances of this class effectively immutable

    It still is possible to do object.__setattr__ to get around it during
    initialization, but usage of this class effectively prevents accidental
    modification, instead requiring explicit modification."""
    inject_immutable_instance(scope)
    return real_type(name, bases, scope)


def inject_immutable_instance(scope):
    """inject immutable __setattr__ and __delattr__ implementations

    see immutable_instance for further details

    :param scope: mapping to modify, inserting __setattr__ and __delattr__
      methods if they're not yet defined.
    """
    scope.setdefault("__setattr__", _immutable_setattr)
    scope.setdefault("__delattr__", _immutable_delattr)


class ImmutableInstance:
    """Class that disables surface-level attribute modifications."""

    __setattr__ = _immutable_setattr
    __delattr__ = _immutable_delattr

    def __getstate__(self):
        return self.__dict__.copy()

    def __setstate__(self, state):
        for k, v in state.items():
            object.__setattr__(self, k, v)
