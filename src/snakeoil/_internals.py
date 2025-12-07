__all__ = ("deprecated",)
from snakeoil.deprecation import Registry

deprecated = Registry("snakeoil")
# See Registry implementation
deprecated.code_directive(
    "snakeoil.deprecation.Registry.is_enabled will always have warnings.deprecated, this must be updated.",
    removal_in_py=(3, 13, 0),
)
