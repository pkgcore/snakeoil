# distutils: language = c

from cpython.mem cimport PyMem_Malloc
from libc.string cimport strdup


cdef extern from "snakeoil/macros.h":
    void SKIP_SLASHES(char *s)


cdef bytes _chars(s):
    if isinstance(s, unicode):
        # encode to the specific encoding used inside of the module
        s = (<unicode>s).encode('utf8')
    return s


def normpath(old_path):
    cdef bytes old_path_bytes = _chars(old_path)
    cdef char *path = old_path_bytes
    cdef char *new_path = strdup(path)
    cdef char *write = new_path
    cdef int depth = 0
    cdef bint is_absolute = '/' == path[0]

    if is_absolute:
        depth -= 1

    while '\0' != path[0]:
        if '/' == path[0]:
            write[0] = '/'
            write += 1
            SKIP_SLASHES(path)
            depth += 1
        elif '.' == path[0]:
            if '.' == path[1] and ('/' == path[2] or '\0' == path[2]):
                if depth == 1:
                    if is_absolute:
                        write = new_path
                    else:
                        # why -2?  because write is at an empty char.
                        # we need to jump back past it and /
                        write -= 2
                        while '/' != write[0]:
                            write -= 1
                    write += 1
                    depth = 0
                elif depth:
                    write -= 2
                    while '/' != write[0]:
                        write -= 1
                    write += 1
                    depth -= 1
                else:
                    if is_absolute:
                        write = new_path + 1
                    else:
                        write[0] = '.'
                        write[1] = '.'
                        write[2] = '/'
                        write += 3
                path += 2
                SKIP_SLASHES(path)
            elif '/' == path[1]:
                path += 2
                SKIP_SLASHES(path)
            elif '\0' == path[1]:
                path += 1
            else:
                write[0] = '.'
                path += 1
                write += 1
        else:
            while '/' != path[0] and '\0' != path[0]:
                write[0] = path[0]
                write += 1
                path += 1

    if write - 1 > new_path and '/' == write[-1]:
        write -= 1

    new_path[write - new_path] = 0
    if isinstance(old_path, unicode):
        return new_path.decode('utf8')
    return new_path


def join(*args):
    if not args:
        raise TypeError("join takes at least one argument (0 given)")

    cdef ssize_t end = len(args)
    cdef ssize_t start = 0, length = 1, i = 0
    cdef bint leading_slash = False

    for i, x in enumerate(args):
        if not isinstance(x, str):
            raise TypeError("all args must be strings")

        if x and '/' == x[0]:
            leading_slash = True
            start = i

    # know the relevant slice now; figure out the size.
    cdef char *s_start
    cdef char *s_end
    cdef char *s

    for i in range(start, end):
        # this is safe because we're using CheckExact above.
        s_start = s = _chars(args[i])
        while '\0' != s[0]:
            s += 1
        if s_start == s:
            continue
        length += s - s_start
        s_end = s
        if i + 1 != end:
            # cut the length down for trailing duplicate slashes
            while s != s_start and '/' == s[-1]:
                s -= 1
            # allocate for a leading slash if needed
            if (s_end == s and (s_start != s or
                (s_end == s_start and i != start))):
                length += 1
            elif s_start != s:
                length -= s_end - s - 1

    # ok... we know the length.  allocate a string, and copy it.
    cdef char *ret = <char *>PyMem_Malloc(length * sizeof(char))
    if not ret:
        raise MemoryError()

    cdef char *tmp_s
    cdef char *buf = ret

    if leading_slash:
        buf[0] = '/'
        buf += 1

    for i in range(start, end):
        s_start = s = _chars(args[i])
        if i == start and leading_slash:
            # a slash is inserted anyways, thus we skip one ahead
            # so it doesn't gain an extra.
            s_start += 1
            s = s_start

        if '\0' == s[0]:
            continue
        while '\0' != s[0]:
            buf[0] = s[0]
            buf += 1
            if '/' == s[0]:
                tmp_s = s + 1
                SKIP_SLASHES(s)
                if '\0' == s[0]:
                    if i + 1  != end:
                        buf -= 1
                    else:
                        # copy the cracked out trailing slashes on the
                        # last item
                        while tmp_s < s:
                            buf[0] = '/'
                            buf += 1
                            tmp_s += 1
                    break
                else:
                    # copy the cracked out intermediate slashes.
                    while tmp_s < s:
                        buf[0] = '/'
                        buf += 1
                        tmp_s += 1
            else:
                s += 1

        if i + 1 != end:
            buf[0] = '/'
            buf += 1

    buf[0] = '\0'
    if isinstance(args[0], unicode):
        return ret.decode('utf8')
    return ret
