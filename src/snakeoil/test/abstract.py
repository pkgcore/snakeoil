__all__ = ("AbstractTest",)
import abc
import inspect


class AbstractTest(abc.ABC):
    """
    Use this class for any abc.ABC test chains you create

    Pytest silently ignores all test classes that are abstract.  This is good... until
    you're filling out a test that you want concrete but either forgot to supply the missing
    thing, or upstream added another abstact.

    In either of those scenarios pytest silently drops the class during collection.

    For subclasses that are *still* intentionally abstract that you do not want pytest
    to collect, pass `still_abstract=True` in the class inheritance.

    For the very first level of an inheritance of this class, it assumes `still_abstract=True`.  All
    derivatives beyond that must be concrete or have that passed.
    """

    def __init_subclass__(cls, still_abstract=False, **kwargs):
        if inspect.isabstract(cls):
            if not still_abstract and AbstractTest not in cls.__bases__:
                raise TypeError(
                    "Test class inherits an abc.ABC that is still abstract; pytest will not collect this.  If you intended it to still be abstract, add `still_abstract=True` to the inherit"
                )
        return super().__init_subclass__(**kwargs)
