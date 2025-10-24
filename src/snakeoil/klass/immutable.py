"""Implementations of immutable instance metaclasses"""

__all__ = ("immutable_instance", "inject_immutable_instance", "ImmutableInstance")
import typing
import warnings

T = typing.TypeVar("T")


def _immutable_setattr(self, attr: str, _value: T) -> T:
    raise AttributeError(self, attr)


def _immutable_delattr(self, attr: str) -> None:
    raise AttributeError(self, attr)


def immutable_instance(
    name: str, bases: tuple[type], scope: dict[str, typing.Any], real_type=type
) -> type:
    """metaclass that makes instances of this class effectively immutable

    It still is possible to do object.__setattr__ to get around it during
    initialization, but usage of this class effectively prevents accidental
    modification, instead requiring explicit modification."""
    inject_immutable_instance(scope)
    return real_type(name, bases, scope)


def inject_immutable_instance(scope: dict[str, typing.Any]):
    """inject immutable __setattr__ and __delattr__ implementations

    see immutable_instance for further details

    :param scope: mapping to modify, inserting __setattr__ and __delattr__
      methods if they're not yet defined.
    """
    scope.setdefault("__setattr__", _immutable_setattr)
    scope.setdefault("__delattr__", _immutable_delattr)


@warnings.deprecated(
    "snakeoil.klass.ImmutableInstance will be removed in future versions.  Use the metaclasses instead"
)
class ImmutableInstance:
    """Class that disables surface-level attribute modifications."""

    __setattr__ = _immutable_setattr
    __delattr__ = _immutable_delattr

    def __getstate__(self) -> dict[str, typing.Any]:
        return self.__dict__.copy()

    def __setstate__(self, state) -> None:
        # This is necessary since any mutation attempts would explode.
        for k, v in state.items():
            object.__setattr__(self, k, v)
