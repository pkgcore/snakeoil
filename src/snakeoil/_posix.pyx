# distutils: language = c
# cython: language_level = 3

from cpython.bytes cimport PyBytes_AS_STRING
from libc.string cimport strdup
from libc.stdio cimport snprintf
from libc.stdlib cimport atoi, malloc, free
from posix.unistd cimport close, getpid


cdef extern from "ctype.h" nogil:
    int isdigit(int c)

cdef extern from "snakeoil/macros.h" nogil:
    void SKIP_SLASHES(char *s)


cdef bytes _chars(s):
    """Convert input string to bytes."""
    if isinstance(s, unicode):
        # encode to the specific encoding used inside of the module
        return (<unicode>s).encode('utf8')
    elif isinstance(s, bytes):
        return s
    else:
        raise TypeError("arg must be str or bytes, not %s" % type(s).__name__)


def normpath(old_path):
    """Normalize a path entry."""
    cdef char *path = strdup(PyBytes_AS_STRING(_chars(old_path)))
    if not path:
        raise MemoryError()
    cdef char *read = path
    cdef char *new_path = strdup(path)
    if not new_path:
        raise MemoryError()
    cdef char *write = new_path
    cdef int depth = 0
    cdef bint is_absolute = b'/' == path[0]

    if is_absolute:
        depth -= 1

    while b'\0' != read[0]:
        if b'/' == read[0]:
            write[0] = b'/'
            write += 1
            SKIP_SLASHES(read)
            depth += 1
        elif b'.' == read[0]:
            if b'.' == read[1] and (b'/' == read[2] or b'\0' == read[2]):
                if depth == 1:
                    if is_absolute:
                        write = new_path
                    else:
                        # why -2?  because write is at an empty char.
                        # we need to jump back past it and /
                        write -= 2
                        while b'/' != write[0]:
                            write -= 1
                    write += 1
                    depth = 0
                elif depth:
                    write -= 2
                    while b'/' != write[0]:
                        write -= 1
                    write += 1
                    depth -= 1
                else:
                    if is_absolute:
                        write = new_path + 1
                    else:
                        write[0] = b'.'
                        write[1] = b'.'
                        write[2] = b'/'
                        write += 3
                read += 2
                SKIP_SLASHES(read)
            elif b'/' == read[1]:
                read += 2
                SKIP_SLASHES(read)
            elif b'\0' == read[1]:
                read += 1
            else:
                write[0] = b'.'
                read += 1
                write += 1
        else:
            while b'/' != read[0] and b'\0' != read[0]:
                write[0] = read[0]
                write += 1
                read += 1

    if write - 1 > new_path and b'/' == write[-1]:
        write -= 1

    new_path[write - new_path] = 0

    cdef bytes py_path
    try:
        py_path = new_path[:write - new_path]
    finally:
        free(new_path)
        free(path)

    if isinstance(old_path, unicode):
        return py_path.decode('utf-8', 'strict')
    return py_path


def join(*args):
    """Join multiple path items."""
    cdef ssize_t end = len(args)
    cdef ssize_t start = 0, length = 0, i = 0
    cdef bint leading_slash = False
    cdef char **paths = <char **>malloc(end * sizeof(char *))

    if not end:
        raise TypeError("join takes at least one argument (0 given)")

    for i in range(end):
        paths[i] = strdup(PyBytes_AS_STRING(_chars(args[i])))

        # find the right most item with a prefixed '/', else 0
        if b'/' == paths[i][0]:
            leading_slash = True
            start = i

    # know the relevant slice now; figure out the size.
    cdef char *s_start
    cdef char *s_end
    cdef char *s

    for i in range(start, end):
        # this is safe because we're checking types above
        s_start = s = paths[i]
        while b'\0' != s[0]:
            s += 1
        if s_start == s:
            continue
        length += s - s_start
        s_end = s
        if i + 1 != end:
            # cut the length down for trailing duplicate slashes
            while s != s_start and b'/' == s[-1]:
                s -= 1
            # allocate for a leading slash if needed
            if (s_end == s and (s_start != s or
                    (s_end == s_start and i != start))):
                length += 1
            elif s_start != s:
                length -= s_end - s - 1

    # ok... we know the length.  allocate a string, and copy it.
    cdef char *ret = <char *>malloc((length + 1) * sizeof(char))
    if not ret:
        raise MemoryError()

    cdef char *tmp_s
    cdef char *buf = ret

    if leading_slash:
        buf[0] = b'/'
        buf += 1

    for i in range(start, end):
        s_start = s = paths[i]
        if i == start and leading_slash:
            # a slash is inserted anyways, thus we skip one ahead
            # so it doesn't gain an extra.
            s_start += 1
            s = s_start

        if b'\0' == s[0]:
            continue
        while b'\0' != s[0]:
            buf[0] = s[0]
            buf += 1
            if b'/' == s[0]:
                tmp_s = s + 1
                SKIP_SLASHES(s)
                if b'\0' == s[0]:
                    if i + 1  != end:
                        buf -= 1
                    else:
                        # copy the cracked out trailing slashes on the
                        # last item
                        while tmp_s < s:
                            buf[0] = b'/'
                            buf += 1
                            tmp_s += 1
                    break
                else:
                    # copy the cracked out intermediate slashes.
                    while tmp_s < s:
                        buf[0] = b'/'
                        buf += 1
                        tmp_s += 1
            else:
                s += 1

        if i + 1 != end:
            buf[0] = b'/'
            buf += 1

    buf[0] = b'\0'

    cdef bytes py_path
    try:
        py_path = ret[:length]
    finally:
        free(ret)
        for i in range(end):
            free(paths[i])
        free(paths)

    if isinstance(args[0], unicode):
        return py_path.decode('utf-8', 'strict')
    return py_path


cdef void slow_closerange(int start, int end):
    cdef int i
    for i in range(start, end):
        close(i)


cdef extern from "dirent.h" nogil:
    cdef struct dirent:
        char *d_name
    ctypedef struct DIR
    int dirfd(DIR *dirp)
    DIR *opendir(char *name)
    int closedir(DIR *dirp)
    dirent *readdir(DIR *dirp)
    int readdir_r(DIR *dirp, dirent *entry, dirent **result)


def closerange(int start, int end):
    """Close a range of fds."""
    cdef int i, fd_dir

    if start >= end:
        return

    cdef DIR *dir_handle
    cdef dirent *entry
    # this is sufficient for a 64-bit pid_t
    cdef char path[32]

    # Note that the version I submitted to python upstream has this in a
    # ALLOW_THREADS block; snakeoils doesn't since it's pointless.
    # Realistically the only time this code is ever ran is immediately post
    # fork- where no threads can be running. Thus no gain to releasing the GIL
    # then reacquiring it, thus we skip it.

    snprintf(path, sizeof(path), "/proc/%i/fd", getpid())

    dir_handle = opendir(path)
    if dir_handle == NULL:
        slow_closerange(start, end)
        return

    fd_dir = dirfd(dir_handle)

    if fd_dir < 0:
        closedir(dir_handle)
        slow_closerange(start, end)
        return

    while True:
        entry = readdir(dir_handle)
        if entry == NULL:
            break

        if not isdigit(entry.d_name[0]):
            continue

        i = atoi(entry.d_name)
        if i >= start and i < end and i != fd_dir:
            close(i)

    closedir(dir_handle)
