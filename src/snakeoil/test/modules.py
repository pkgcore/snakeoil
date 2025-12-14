__all__ = ("ExportedModules",)
from snakeoil._internals import deprecated


@deprecated(
    "This was broken and accidentally disabled long ago, and is a no-op.  Use snakeoil.test.code_quality.Modules",
    removal_in=(0, 12, 0),
)
class ExportedModules:
    pass
