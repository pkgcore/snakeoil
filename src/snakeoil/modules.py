"""
dynamic import functionality
"""

__all__ = ("FailedImport", "load_attribute", "load_any")

from importlib import import_module

from snakeoil._internals import deprecated


class FailedImport(ImportError):
    """
    Raised when a requested target cannot be imported
    """

    def __init__(self, trg, e):
        super().__init__(self, f"Failed importing target '{trg}': '{e}'")
        self.trg, self.e = trg, e


@deprecated(
    "Use importlib.import_module's package argument",
    removal_in=(0, 12, 0),
)
def load_attribute(name):
    """load an attribute from a module

    :param name: python dotted namespace path of the attribute to load from a
        module for example.
    :raise: FailedImport if importing fails, or the requested attribute cannot
        be found
    :return: attribute resolved from `name`
    """
    chunks = name.rsplit(".", 1)
    if len(chunks) == 1:
        raise FailedImport(name, "it isn't an attribute, it's a module")
    try:
        return getattr(import_module(chunks[0]), chunks[1])
    except (AttributeError, ImportError) as exc:
        # try to show actual import error if it exists
        try:
            import_module(name)
        except ImportError as exc:
            raise FailedImport(name, exc) from exc
        raise FailedImport(name, exc) from exc


@deprecated(
    "Use importlib.import_module's package argument",
    removal_in=(0, 12, 0),
)
def load_any(name):
    """
    load an attribute or a module from a namespace

    """

    try:
        return import_module(name)
    except ImportError:
        return load_attribute(name)
    except Exception as exc:
        raise FailedImport(name, exc) from exc
