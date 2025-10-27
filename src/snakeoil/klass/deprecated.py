"""Implementations of immutable instance metaclasses"""

__all__ = ("immutable_instance", "inject_immutable_instance", "ImmutableInstance")

import typing

from snakeoil.deprecation import deprecated, suppress_deprecation_warning


@deprecated("Use snakeoil.klass.meta.Immutable* metaclasses instead")
def immutable_instance(
    name: str, bases: tuple[type], scope: dict[str, typing.Any], real_type=type
) -> type:
    """metaclass that makes instances of this class effectively immutable

    It still is possible to do object.__setattr__ to get around it during
    initialization, but usage of this class effectively prevents accidental
    modification, instead requiring explicit modification."""
    with suppress_deprecation_warning():
        inject_immutable_instance(scope)
    return real_type(name, bases, scope)


@deprecated("Use snakeoil.klass.meta.Immutable* metaclasses instead")
class ImmutableInstance:
    """Class that disables surface-level attribute modifications."""

    def __setattr__(self, attr, _value):
        raise AttributeError(self, attr)

    def __delattr__(self, attr):
        raise AttributeError(self, attr)

    def __getstate__(self) -> dict[str, typing.Any]:
        return self.__dict__.copy()

    def __setstate__(self, state) -> None:
        # This is necessary since any mutation attempts would explode.
        for k, v in state.items():
            object.__setattr__(self, k, v)


@deprecated("Use snakeoil.klass.meta.Immutable* metaclasses instead")
def inject_immutable_instance(scope: dict[str, typing.Any]):
    """inject immutable __setattr__ and __delattr__ implementations

    see immutable_instance for further details

    :param scope: mapping to modify, inserting __setattr__ and __delattr__
      methods if they're not yet defined.
    """
    scope.setdefault("__setattr__", ImmutableInstance.__setattr__)
    scope.setdefault("__delattr__", ImmutableInstance.__delattr__)
