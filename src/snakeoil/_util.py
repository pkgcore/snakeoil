__all__ = ("deprecated",)

try:
    from warnings import deprecated  # pyright: ignore[reportAssignmentType]
except ImportError:

    def deprecated(_message):
        """
        This is a noop; deprecation warnings are disabled for pre python
        3.13.
        """

        def f(thing):
            return thing

        return f
