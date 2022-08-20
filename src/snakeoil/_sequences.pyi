from typing import Any, Callable, Iterable, Type

def iflatten_instance(l: Iterable, skip_flattening: Iterable[Type] = (str, bytes)) -> Iterable:
    ...

def iflatten_func(l: Iterable, skip_func: Callable[[Any], bool]) -> Iterable:
    ...
