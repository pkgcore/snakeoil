# distutils: language = c
# cython: language_level = 3

_str_kls = (str, bytes)
def iflatten_instance(l, skip_flattening=_str_kls):
    """collapse [[1],2] into [1,2]

    :param skip_flattening: list of classes to not descend through
    :return: this generator yields each item that cannot be flattened (or is
        skipped due to being a instance of ``skip_flattening``)
    """
    cdef list store
    if isinstance(l, skip_flattening):
        yield l
        return
    current = iter(l)
    store = [current]
    while True:
        try:
            x = next(current)
        except StopIteration:
            store.pop()
            if store:
                current = store[-1]
                continue
            else:
                return
        if (hasattr(x, '__iter__')
                and not isinstance(x, skip_flattening)
                # prevent infinite descend in case of single characters
                and not (isinstance(x, _str_kls) and len(x) == 1)):
            current = iter(x)
            store.append(current)
        else:
            yield x

def iflatten_func(l, skip_func):
    """collapse [[1],2] into [1,2]

    :param skip_func: a callable that returns True when iflatten_func should
        descend no further
    :return: this generator yields each item that cannot be flattened (or is
        skipped due to a True result from skip_func)
    """
    cdef list store
    if skip_func(l):
        yield l
        return
    current = iter(l)
    store = [current]
    while True:
        try:
            x = next(current)
        except StopIteration:
            store.pop()
            if store:
                current = store[-1]
                continue
            else:
                return
        if hasattr(x, '__iter__') and not skip_func(x):
            current = iter(x)
            store.append(current)
        else:
            yield x
