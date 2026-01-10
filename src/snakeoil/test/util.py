__all__ = ("NamespaceCollector",)
import inspect
import types
import typing

import pytest

from snakeoil import klass
from snakeoil.python_namespaces import get_submodules_of
from snakeoil.test import AbstractTest


class NamespaceCollector(AbstractTest):
    namespaces: tuple[str] = klass.abstractclassvar(tuple[str])
    namespace_ignores: tuple[str, ...] = ()

    strict_configurable_tests: typing.ClassVar[tuple[str, ...]] = ()
    strict: typing.ClassVar[typing.Literal[True] | tuple[str, ...]] = ()

    def __init_subclass__(cls, **kwargs) -> None:
        if not inspect.isabstract(cls):
            targets = cls.strict_configurable_tests
            strict = targets if cls.strict is True else cls.strict
            for test_name in cls.strict_configurable_tests:
                if test_name not in strict:
                    setattr(cls, test_name, pytest.mark.xfail(getattr(cls, test_name)))

        return super().__init_subclass__(**kwargs)

    @classmethod
    def collect_modules(cls) -> typing.Iterable[types.ModuleType]:
        for namespace in cls.namespaces:
            yield from get_submodules_of(
                namespace,
                dont_import=cls.namespace_ignores,
                include_root=True,
            )
