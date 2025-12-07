__all__ = ("ExportedModules",)
from snakeoil._internals import deprecated


@deprecated("ExportedModules does nothing.  Use snakeoil.test.code_quality.Modules")
class ExportedModules:
    pass
