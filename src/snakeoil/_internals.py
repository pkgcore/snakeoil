__all__ = ("deprecated",)
import snakeoil
from snakeoil.deprecation import Registry

deprecated = Registry(
    "snakeoil",
    version=snakeoil.__version_info__,
    python_mininum_version=snakeoil.__python_mininum_version__,
)
# See Registry implementation
deprecated.code_directive(
    "snakeoil.deprecation.Registry.is_enabled will always have warnings.deprecated, this must be updated.",
    removal_in_python=(3, 13, 0),
)
