__all__ = ("ExportedModules",)
from snakeoil.deprecation import deprecated


@deprecated("ExportedModules does nothing.  Use snakeoil.test.code_quality.Modules")
class ExportedModules:
    pass
