# distutils: language = c

from cpython.mem cimport PyMem_Malloc
from cpython.bytes cimport PyBytes_AsString
from libc.string cimport strdup
from libc.stdio cimport snprintf
from libc.stdlib cimport atoi
from posix.unistd cimport close, getpid


cdef extern from "ctype.h" nogil:
    int isdigit(int c)

cdef extern from "snakeoil/macros.h" nogil:
    void SKIP_SLASHES(char *s)


cdef bytes _chars(s):
    """Convert input string to bytes."""
    if isinstance(s, unicode):
        # encode to the specific encoding used inside of the module
        s = (<unicode>s).encode('utf8')
    return s


def normpath(old_path):
    """Normalize a path entry."""
    cdef char *path = PyBytes_AsString(_chars(old_path))
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
        return new_path.decode()
    return new_path


def join(*args):
    """Join multiple path items."""
    if not len(args):
        raise TypeError("join takes at least one argument (0 given)")

    cdef ssize_t end = len(args)
    cdef ssize_t start = 0, length = 0, i = 0
    cdef bint leading_slash = False

    for i in xrange(end):
        if not isinstance(args[i], str):
            raise TypeError("all args must be strings")

        if len(args[i]) and '/' == args[i][0]:
            leading_slash = True
            start = i

    # know the relevant slice now; figure out the size.
    cdef char *s_start
    cdef char *s_end
    cdef char *s

    for i in xrange(start, end):
        # this is safe because we're using CheckExact above.
        s_start = s = PyBytes_AsString(_chars(args[i]))
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
    cdef char *ret = <char *>PyMem_Malloc((length + 1) * sizeof(char))
    if not ret:
        raise MemoryError()

    cdef char *tmp_s
    cdef char *buf = ret

    if leading_slash:
        buf[0] = '/'
        buf += 1

    for i in xrange(start, end):
        s_start = s = PyBytes_AsString(_chars(args[i]))
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
        return ret.decode()
    return ret


cdef void slow_closerange(int start, int end):
    cdef int i
    for i in xrange(start, end):
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

cdef extern from "osdefs.h" nogil:
    enum: MAXPATHLEN


def closerange(int start, int end):
    """Close a range of fds."""
    cdef int i, fd_dir

    if start >= end:
        return

    cdef DIR *dir_handle
    cdef dirent *entry
    cdef char path[MAXPATHLEN]

    # Note that the version I submitted to python upstream has this in a
    # ALLOW_THREADS block; snakeoils doesn't since it's pointless.
    # Realistically the only time this code is ever ran is immediately post
    # fork- where no threads can be running. Thus no gain to releasing the GIL
    # then reacquiring it, thus we skip it.

    snprintf(path, MAXPATHLEN, "/proc/%i/fd", getpid())

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
