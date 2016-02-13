/*
 * Copyright: 2006-2011 Brian Harring <ferringb@gmail.com>
 * License: GPL2/BSD
 *
 * C version of some of snakeoil (for extra speed).
 */

/* This does not really do anything since we do not use the "#"
 * specifier in a PyArg_Parse or similar call, but hey, not using it
 * means we are Py_ssize_t-clean too!
 */

#define PY_SSIZE_T_CLEAN

#include "snakeoil/common.h"
#include <structmember.h>
#include <sys/mman.h>
#include <sys/types.h>
#include <dirent.h>
#include <sys/stat.h>
#include <fcntl.h>

// we get MAXPATHLEN from python.
#include <osdefs.h>


static PyObject *snakeoil_stat_float_times = NULL;
static PyObject *snakeoil_empty_tuple = NULL;
static PyObject *snakeoil_readlines_empty_iter_singleton = NULL;
static PyObject *snakeoil_native_readfile_shim = NULL;
static PyObject *snakeoil_native_readlines_shim = NULL;


#define SKIP_SLASHES(ptr) while ('/' == *(ptr)) (ptr)++;


static PyObject *
snakeoil_normpath(PyObject *self, PyObject *py_old_path)
{
	if (!PyString_CheckExact(py_old_path)) {
		PyErr_SetString(PyExc_TypeError,
			"old_path must be a str");
		return NULL;
	}
	Py_ssize_t path_len = PyString_GET_SIZE(py_old_path);
	if (!path_len)
		return PyString_FromString(".");

	char *path = PyString_AS_STRING(py_old_path);

	PyObject *new_obj = PyString_FromStringAndSize(NULL, path_len);
	if (!new_obj)
		return new_obj;
	char *new_path = PyString_AS_STRING(new_obj);
	char *write = new_path;
	int depth = 0;
	int is_absolute = '/' == *path;

	if (is_absolute) {
		depth--;
	}

	while ('\0' != *path) {
			if ('/' == *path) {
				*write = '/';
				write++;
				SKIP_SLASHES(path);
				depth++;
			} else if ('.' == *path) {
				if ('.' == path[1] && ('/' == path[2] || '\0' == path[2])) {
					if (1 == depth) {
						if (is_absolute) {
							write = new_path;
						} else {
							// why -2?  because write is at an empty char.
							// we need to jump back past it and /
							write -= 2;
							while ('/' != *write)
								write--;
						}
						write++;
						depth = 0;
					} else if (depth) {
						write -= 2;
						while ('/' != *write)
							write--;
						write++;
						depth--;
					} else {
						if (is_absolute) {
							write = new_path + 1;
						} else {
							write[0] = '.';
							write[1] = '.';
							write[2] = '/';
							write += 3;
						}
					}
					path += 2;
					SKIP_SLASHES(path);
				} else if ('/' == path[1]) {
					path += 2;
					SKIP_SLASHES(path);
				} else if ('\0' == path[1]) {
					path++;
				} else {
					*write = '.';
					path++;
					write++;
				}
			} else {
				while ('/' != *path && '\0' != *path) {
					*write = *path;
					write++;
					path++;
				}
			}
	}
	if (write -1 > new_path && '/' == write[-1])
		write--;

	_PyString_Resize(&new_obj, write - new_path);
	return new_obj;
}

static PyObject *
snakeoil_join(PyObject *self, PyObject *args)
{
	if (!args) {
		PyErr_SetString(PyExc_TypeError, "requires at least one path");
		return NULL;
	}
	PyObject *fast = PySequence_Fast(args, "arg must be a sequence");
	if (!fast)
		return NULL;
	Py_ssize_t end = PySequence_Fast_GET_SIZE(fast);
	if (!end) {
		PyErr_SetString(PyExc_TypeError,
			"join takes at least one argument (0 given)");
		return NULL;
	}

	PyObject **items = PySequence_Fast_ITEMS(fast);
	Py_ssize_t start = 0, len, i = 0;
	char *s;
	int leading_slash = 0;
	// find the right most item with a prefixed '/', else 0.
	for (; i < end; i++) {
		if (!PyString_CheckExact(items[i])) {
			PyErr_SetString(PyExc_TypeError, "all args must be strings");
			Py_DECREF(fast);
			return NULL;
		}
		s = PyString_AsString(items[i]);
		if ('/' == *s) {
			leading_slash = 1;
			start = i;
		}
	}
	// know the relevant slice now; figure out the size.
	len = 0;
	char *s_start;
	for (i = start; i < end; i++) {
		// this is safe because we're using CheckExact above.
		s_start = s = PyString_AS_STRING(items[i]);
		while ('\0' != *s)
			s++;
		if (s_start == s)
			continue;
		len += s - s_start;
		char *s_end = s;
		if (i + 1 != end) {
			// cut the length down for trailing duplicate slashes
			while (s != s_start && '/' == s[-1])
				s--;
			// allocate for a leading slash if needed
			if (s_end == s && (s_start != s ||
				(s_end == s_start && i != start))) {
				len++;
			} else if (s_start != s) {
				len -= s_end - s -1;
			}
		}
	}

	// ok... we know the length.  allocate a string, and copy it.
	PyObject *ret = PyString_FromStringAndSize(NULL, len);
	if (!ret)
		return NULL;
	char *buf = PyString_AS_STRING(ret);
	if (leading_slash) {
		*buf = '/';
		buf++;
	}
	for (i = start; i < end; i++) {
		s_start = s = PyString_AS_STRING(items[i]);
		if (i == start && leading_slash) {
			// a slash is inserted anywas, thus we skip one ahead
			// so it doesn't gain an extra.
			s_start++;
			s = s_start;
		}

	   if ('\0' == *s)
			continue;
		while ('\0' != *s) {
			*buf = *s;
			buf++;
			if ('/' == *s) {
				char *tmp_s = s + 1;
				SKIP_SLASHES(s);
				if ('\0' == *s) {
					if (i + 1  != end) {
						buf--;
					} else {
						// copy the cracked out trailing slashes on the
						// last item
						while (tmp_s < s) {
							*buf = '/';
							buf++;
							tmp_s++;
						}
					}
					break;
				} else {
					// copy the cracked out intermediate slashes.
					while (tmp_s < s) {
						*buf = '/';
						buf++;
						tmp_s++;
					}
				}
			} else
				s++;
		}
		if (i + 1 != end) {
			*buf = '/';
			buf++;
		}
	}
	*buf = '\0';
	Py_DECREF(fast);
	return ret;
}

// returns 0 on success opening, 1 on ENOENT but ignore, and -1 on failure
// if failure condition, appropriate exception is set.

static inline int
snakeoil_read_open_and_stat(PyObject *path, int *fd, struct stat *st)
{
	errno = 0;
	if ((*fd = open(PyString_AsString(path), O_RDONLY)) >= 0) {
		int ret = fstat(*fd, st);
		if (!ret) {
			return 0;
		}
	}
	return 1;
}

static inline int
handle_failed_open_stat(int fd, PyObject *path, PyObject *swallow_missing)
{
	if (fd < 0) {
		if (errno == ENOENT || errno == ENOTDIR) {
			if (swallow_missing) {
				int result = PyObject_IsTrue(swallow_missing);
				if (result == -1) {
					return 1;
				} else if (result) {
					errno = 0;
					return 0;
				}
			}
		}
		PyErr_SetFromErrnoWithFilenameObject(PyExc_IOError, path);
		return 1;
	}
	PyErr_SetFromErrnoWithFilenameObject(PyExc_OSError, path);
	if (close(fd))
		PyErr_SetFromErrnoWithFilenameObject(PyExc_IOError, path);
	return 1;
}

static PyObject *
snakeoil_readfile(PyObject *self, PyObject *args)
{
	PyObject *path, *swallow_missing = NULL;
	if (!args || !PyArg_ParseTuple(args, "S|O:readfile", &path,
		&swallow_missing)) {
		return NULL;
	}
//	Py_ssize_t size;
	int fd, ret;
	struct stat st;
	Py_BEGIN_ALLOW_THREADS
	ret = snakeoil_read_open_and_stat(path, &fd, &st);
	Py_END_ALLOW_THREADS
	if (ret) {
		if (handle_failed_open_stat(fd, path, swallow_missing))
			return NULL;
		Py_RETURN_NONE;
	}

	if (0 == st.st_size) {
		// we're either dealing with an empty file, or a virtual fs
		// that doesn't return proper stat information
		char buf[1];
		size_t ret = read(fd, buf, 1);
		close(fd);
		if (ret == 0) {
			return PyString_FromStringAndSize(NULL, 0);
		} else if (ret == 1) {
			// procfs, fallback to native.
			return PyObject_Call(snakeoil_native_readfile_shim, args, NULL);
		}
	}

	PyObject *data = PyString_FromStringAndSize(NULL, st.st_size);

	if (!data) {
		close(fd);
		return (PyObject *)NULL;
	}

	size_t actual_read = 0;
	Py_BEGIN_ALLOW_THREADS
	errno = 0;
	actual_read = read(fd, PyString_AS_STRING(data), st.st_size);
	close(fd);
	Py_END_ALLOW_THREADS

	if (actual_read != st.st_size) {
		// if no error, then sysfs/virtual fs gave us bad stat data.
		if (0 != errno) {
			Py_DECREF(data);
			data = PyErr_SetFromErrnoWithFilenameObject(PyExc_OSError, path);
		} else {
			// note that if this fails, it'll wipe data and set an appropriate
			// exception.
			_PyString_Resize(&data, actual_read);
		}
	}

	return data;
}

typedef struct {
	PyObject_HEAD
} snakeoil_readlines_empty_iter;

static PyObject *
snakeoil_readlines_empty_iter_get_mtime(snakeoil_readlines_empty_iter *self)
{
	Py_RETURN_NONE;
}

static int
snakeoil_readlines_empty_iter_set_mtime(snakeoil_readlines_empty_iter *self,
	PyObject *v, void *closure)
{
	PyErr_SetString(PyExc_AttributeError, "mtime is immutable");
	return -1;
}

static PyObject *
snakeoil_readlines_empty_iter_next(snakeoil_readlines_empty_iter *self)
{
	PyErr_SetNone(PyExc_StopIteration);
	return NULL;
}

struct PyGetSetDef snakeoil_readlines_empty_iter_getsetters[] = {
	snakeoil_GETSET(snakeoil_readlines_empty_iter, "mtime", mtime),
	{NULL}
};

static PyTypeObject snakeoil_readlines_empty_iter_type = {
	PyObject_HEAD_INIT(NULL)
	0,											   /* ob_size */
	"readlines.empty_iter",						  /* tp_name */
	sizeof(snakeoil_readlines_empty_iter),			/* tp_size */
	0,											   /* tp_itemsize*/
	0,											   /* tp_dealloc*/
	0,											   /* tp_print*/
	0,											   /* tp_getattr*/
	0,											   /* tp_setattr*/
	0,											   /* tp_compare*/
	0,											   /* tp_repr*/
	0,											   /* tp_as_number*/
	0,											   /* tp_as_sequence*/
	0,											   /* tp_as_mapping*/
	0,											   /* tp_hash */
	(ternaryfunc)0,								  /* tp_call*/
	(reprfunc)0,									 /* tp_str*/
	0,											   /* tp_getattro*/
	0,											   /* tp_setattro*/
	0,											   /* tp_as_buffer*/
	Py_TPFLAGS_DEFAULT,							  /* tp_flags*/
	0,											   /* tp_doc */
	(traverseproc)0,								 /* tp_traverse */
	(inquiry)0,									  /* tp_clear */
	(richcmpfunc)0,								  /* tp_richcompare */
	0,											   /* tp_weaklistoffset */
	(getiterfunc)PyObject_SelfIter,				  /* tp_iter */
	(iternextfunc)snakeoil_readlines_empty_iter_next, /* tp_iternext */
	0,											   /* tp_methods */
	0,											   /* tp_members */
	snakeoil_readlines_empty_iter_getsetters,		 /* tp_getset */
};

typedef struct {
	PyObject_HEAD
	char *start;
	char *end;
	char *map;
	int fd;
	int strip_whitespace;
	time_t mtime;
	unsigned long mtime_nsec;
	PyObject *fallback;
} snakeoil_readlines;

static PyObject *
snakeoil_readlines_new(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
	PyObject *path, *swallow_missing = NULL, *strip_whitespace = NULL;
	PyObject *none_on_missing = NULL;
	snakeoil_readlines *self = NULL;
	if (kwargs && PyDict_Size(kwargs)) {
		PyErr_SetString(PyExc_TypeError,
			"readlines.__new__ doesn't accept keywords");
		return NULL;
	} else if (!PyArg_ParseTuple(args, "S|OOOO:readlines.__new__",
		&path, &strip_whitespace, &swallow_missing, &none_on_missing)) {
		return NULL;
	}

	int fd;
	struct stat st;
	size_t size;
	void *ptr = NULL;
	PyObject *fallback = NULL;
	Py_BEGIN_ALLOW_THREADS
	errno = 0;
	if (snakeoil_read_open_and_stat(path, &fd, &st)) {
		Py_BLOCK_THREADS

		if (handle_failed_open_stat(fd, path, swallow_missing))
			return NULL;

		// return an empty tuple, and let them iter over that.
		if (none_on_missing && PyObject_IsTrue(none_on_missing)) {
			Py_RETURN_NONE;
		}

		Py_INCREF(snakeoil_readlines_empty_iter_singleton);
		return snakeoil_readlines_empty_iter_singleton;
	}
	size = st.st_size;
	if (st.st_size == 0) {
		// procfs is known to lie; do a read check.
		char buf[1];
		int ret = read(fd, buf, 1);
		close(fd);
		Py_BLOCK_THREADS

		if (ret == 0) {
			// actual empty file.
			Py_INCREF(snakeoil_readlines_empty_iter_singleton);
			return snakeoil_readlines_empty_iter_singleton;
		} else if (ret == 1) {
			// procfs.  fallback to native.
			return PyObject_Call(snakeoil_native_readlines_shim, args, kwargs);
		}
		// no clue how it could happen, but handle it.
		ptr = MAP_FAILED;

	} else if (st.st_size >= 0x4000) {
		ptr = (char *)mmap(NULL, st.st_size, PROT_READ,
			MAP_SHARED|MAP_NORESERVE, fd, 0);
		if (ptr == MAP_FAILED) {
	        // for this to occur, either mmap isn't support, or it's sysfs and gave
			// us bad stat data, or the file changed under our feet.  Either way,
			// leave it for native to handle.
			close(fd);
			Py_BLOCK_THREADS
			return PyObject_Call(snakeoil_native_readlines_shim, args, kwargs);
		}

	} else {
		Py_BLOCK_THREADS
		fallback = PyString_FromStringAndSize(NULL, st.st_size);
		Py_UNBLOCK_THREADS
		if (fallback) {
			errno = 0;
			size_t actual_read = read(fd, PyString_AS_STRING(fallback), st.st_size);
			if (actual_read != st.st_size) {
				// we reset the size since syfs (and other virtual filesystems) lie
				// and report a st_size of 4096 (for example), but have less data.
				size = actual_read;
				if (0 != errno) {
					// actual error occured;
					ptr = MAP_FAILED;
				}
			} else {
				ptr = NULL;
			}
		}
		int ret = close(fd);
		if (ret) {
			Py_CLEAR(fallback);
			PyErr_SetFromErrnoWithFilenameObject(PyExc_OSError, path);
			Py_BLOCK_THREADS
			return NULL;
		} else if (!fallback) {
			Py_BLOCK_THREADS
			return NULL;
		}
	}
	Py_END_ALLOW_THREADS

	if (ptr == MAP_FAILED) {
		PyErr_SetFromErrnoWithFilenameObject(PyExc_OSError, path);
		if (close(fd))
			PyErr_SetFromErrnoWithFilenameObject(PyExc_OSError, path);
		Py_CLEAR(fallback);
		return NULL;
	}

	// cleanup now that we've got the gil; resize only if needed.
	if (size != st.st_size && fallback) {
		if (-1 == _PyString_Resize(&fallback, st.st_size)) {
			return (PyObject *)NULL;
		}
	}

	self = (snakeoil_readlines *)type->tp_alloc(type, 0);
	if (!self) {
		// you've got to be kidding me...
		if (ptr) {
			munmap(ptr, st.st_size);
			close(fd);
			errno = 0;
		} else {
			Py_DECREF(fallback);
		}
		if (self) {
			Py_DECREF(self);
		}
		return NULL;
	}
	self->fallback = fallback;
	self->map = ptr;
	self->mtime = st.st_mtime;
#ifdef HAVE_STAT_TV_NSEC
	self->mtime_nsec = st.st_mtim.tv_nsec;
#else
	self->mtime_nsec = 0;
#endif
	if (ptr) {
		self->start = ptr;
		self->fd = fd;
	} else {
		self->start = PyString_AS_STRING(fallback);
		self->fd = -1;
	}
	self->end = self->start + size;

	if (strip_whitespace) {
		if (strip_whitespace == Py_True) {
			self->strip_whitespace = 1;
		} else if (strip_whitespace == Py_False) {
			self->strip_whitespace = 0;
		} else {
			if (-1 == (self->strip_whitespace = PyObject_IsTrue(strip_whitespace))) {
				Py_DECREF(self);
				return NULL;
			}
		}
	} else
		self->strip_whitespace = 1;
	return (PyObject *)self;
}

static void
snakeoil_readlines_dealloc(snakeoil_readlines *self)
{
	if (self->fallback) {
		Py_DECREF(self->fallback);
	} else if (self->map) {
		if (munmap(self->map, self->end - self->map))
			// swallow it, no way to signal an error
			errno = 0;
		if (close(self->fd))
			// swallow it, no way to signal an error
			errno = 0;
	}
	self->ob_type->tp_free((PyObject *)self);
}

static PyObject *
snakeoil_readlines_iternext(snakeoil_readlines *self)
{
	if (self->start == self->end) {
		// at the end, thus return
		return NULL;
	}
	char *p = self->start;
	assert(self->end);
	assert(self->start);
	assert(self->map || self->fallback);
	assert(self->end > self->start);

	p = memchr(p, '\n', self->end - p);
	if (!p)
		p = self->end;

	PyObject *ret;
	if (self->strip_whitespace) {
		char *real_start = self->start;
		char *real_end = p;
		while (real_start < p && isspace(*real_start)) {
			real_start++;
		}
		while (real_start < real_end && isspace(real_end[-1])) {
			real_end--;
		}
		ret = PyString_FromStringAndSize(real_start, real_end - real_start);
	} else {
		if (p == self->end)
			ret = PyString_FromStringAndSize(self->start, p - self->start);
		else
			ret = PyString_FromStringAndSize(self->start, p - self->start + 1);
	}
	if (p != self->end) {
		p++;
	}
	self->start = p;
	return ret;
}

static int
snakeoil_readlines_set_mtime(snakeoil_readlines *self, PyObject *v,
	void *closure)
{
	PyErr_SetString(PyExc_AttributeError, "mtime is immutable");
	return -1;
}

static PyObject *
snakeoil_readlines_get_mtime(snakeoil_readlines *self)
{
	PyObject *ret = PyObject_CallFunctionObjArgs(snakeoil_stat_float_times, NULL);
	if (!ret)
		return NULL;
	int is_float;
	if (ret == Py_True) {
		is_float = 1;
	} else if (ret == Py_False) {
		is_float = 0;
	} else {
		is_float = PyObject_IsTrue(ret);
		if (is_float == -1) {
			Py_DECREF(ret);
			return NULL;
		}
	}
	Py_DECREF(ret);
	if (is_float)
		return PyFloat_FromDouble(self->mtime + 1e-9 * self->mtime_nsec);
#ifdef TIME_T_LONGER_THAN_LONG
	return PyLong_FromLong((Py_LONG_LONG)self->mtime);
#else
	return PyInt_FromLong((long)self->mtime);
#endif
}

static PyGetSetDef snakeoil_readlines_getsetters[] = {
snakeoil_GETSET(snakeoil_readlines, "mtime", mtime),
	{NULL}
};

PyDoc_STRVAR(
	snakeoil_readlines_documentation,
	"readline(path [, strip_newlines [, swallow_missing [, none_on_missing]]])"
	" -> iterable yielding"
	" each line of a file\n\n"
	"if strip_newlines is True, the trailing newline is stripped\n"
	"if swallow_missing is True, for missing files it returns an empty "
	"iterable\n"
	"if none_on_missing and the file is missing, return None instead"
	);


static PyTypeObject snakeoil_readlines_type = {
	PyObject_HEAD_INIT(NULL)
	0,											   /* ob_size*/
	"snakeoil._posix.readlines",				 /* tp_name*/
	sizeof(snakeoil_readlines),					   /* tp_basicsize*/
	0,											   /* tp_itemsize*/
	(destructor)snakeoil_readlines_dealloc,		   /* tp_dealloc*/
	0,											   /* tp_print*/
	0,											   /* tp_getattr*/
	0,											   /* tp_setattr*/
	0,											   /* tp_compare*/
	0,											   /* tp_repr*/
	0,											   /* tp_as_number*/
	0,											   /* tp_as_sequence*/
	0,											   /* tp_as_mapping*/
	0,											   /* tp_hash */
	(ternaryfunc)0,								  /* tp_call*/
	(reprfunc)0,									 /* tp_str*/
	0,											   /* tp_getattro*/
	0,											   /* tp_setattro*/
	0,											   /* tp_as_buffer*/
	Py_TPFLAGS_DEFAULT,							  /* tp_flags*/
	snakeoil_readlines_documentation,				 /* tp_doc */
	(traverseproc)0,								 /* tp_traverse */
	(inquiry)0,									  /* tp_clear */
	(richcmpfunc)0,								  /* tp_richcompare */
	0,											   /* tp_weaklistoffset */
	(getiterfunc)PyObject_SelfIter,				  /* tp_iter */
	(iternextfunc)snakeoil_readlines_iternext,		/* tp_iternext */
	0,											   /* tp_methods */
	0,											   /* tp_members */
	snakeoil_readlines_getsetters,					/* tp_getset */
	0,											   /* tp_base */
	0,											   /* tp_dict */
	0,											   /* tp_descr_get */
	0,											   /* tp_descr_set */
	0,											   /* tp_dictoffset */
	(initproc)0,									 /* tp_init */
	0,											   /* tp_alloc */
	snakeoil_readlines_new,						   /* tp_new */
};

void
snakeoil_slow_closerange(int from, int to)
{
	int i;
	for (i = from; i < to; i++)
		close(i);
}

static PyObject *
snakeoil_closerange(PyObject *self, PyObject *args)
{
	int from, to, i, fd_dir;
	DIR *dir_handle;
	struct dirent *entry;
	char path[MAXPATHLEN];

	if (!PyArg_ParseTuple(args, "ii:closerange", &from, &to))
		return NULL;

	if (from >= to) {
		Py_RETURN_NONE;
	}

	// Note that the version I submitted to python upstream
	// has this in a ALLOW_THREADS block; snakeoils doesn't
	// since it's pointless.  Realistically the only time
	// this code is ever ran is immediately post fork-
	// where no threads can be running.  Thus no gain
	// to releasing the GIL then reacquiring it, thus we
	// skip it.

	PyOS_snprintf(path, MAXPATHLEN, "/proc/%i/fd", getpid());

	if (!(dir_handle = opendir(path))) {
		snakeoil_slow_closerange(from, to);
		Py_RETURN_NONE;
	}

	fd_dir = dirfd(dir_handle);

	if (fd_dir < 0) {
		closedir(dir_handle);
		snakeoil_slow_closerange(from, to);
		Py_RETURN_NONE;
	}

	while (entry = readdir(dir_handle)) {
		if (!isdigit(entry->d_name[0])) {
			continue;
		}

		i = atoi(entry->d_name);
		if (i >= from && i < to && i != fd_dir) {
			close(i);
		}
	}
	closedir(dir_handle);

	Py_RETURN_NONE;
}


static PyMethodDef snakeoil_posix_methods[] = {
	{"normpath", (PyCFunction)snakeoil_normpath, METH_O,
		"normalize a path entry"},
	{"join", snakeoil_join, METH_VARARGS,
		"join multiple path items"},
	{"readfile", snakeoil_readfile, METH_VARARGS,
		"fast read of a file: requires a string path, and an optional bool "
		"indicating whether to swallow ENOENT; defaults to false"},
	{"closerange", (PyCFunction)snakeoil_closerange, METH_VARARGS,
		"close a range of fds"},
	{NULL}
};


PyDoc_STRVAR(
	snakeoil_posix_documentation,
	"cpython posix path functionality");

PyMODINIT_FUNC
init_posix(void)
{
	snakeoil_LOAD_SINGLE_ATTR(snakeoil_stat_float_times, "os", "stat_float_times");

	snakeoil_empty_tuple = PyTuple_New(0);
	if (!snakeoil_empty_tuple)
		return;

	PyObject *m = Py_InitModule3("_posix", snakeoil_posix_methods,
								 snakeoil_posix_documentation);
	if (!m)
		return;

	if (PyType_Ready(&snakeoil_readlines_type) < 0)
		return;

	if (PyType_Ready(&snakeoil_readlines_empty_iter_type) < 0)
		return;

	Py_INCREF(&snakeoil_readlines_empty_iter_type);
	snakeoil_readlines_empty_iter_singleton = _PyObject_New(
		&snakeoil_readlines_empty_iter_type);


	Py_INCREF(&snakeoil_readlines_type);
	if (PyModule_AddObject(
			m, "readlines", (PyObject *)&snakeoil_readlines_type) == -1)
		return;

	snakeoil_LOAD_SINGLE_ATTR(snakeoil_native_readlines_shim, "snakeoil._fileutils",
		"_native_readlines_shim");
	snakeoil_LOAD_SINGLE_ATTR(snakeoil_native_readfile_shim, "snakeoil._fileutils",
		"_native_readfile_shim");

	/* Success! */
}
