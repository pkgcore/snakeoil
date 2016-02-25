/*
 * Copyright: 2006-2011 Brian Harring <ferringb@gmail.com>
 * Copyright: 2006-2007 Marien Zwart <marienz@gentoo.org>
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

#include <dirent.h>
#include <sys/stat.h>

#ifndef HAVE_DIRENT_D_TYPE
#	define DT_DIR 0
#	define DT_REG 0
#endif


static PyObject *snakeoil_DIRSTR,
	*snakeoil_CHRSTR,
	*snakeoil_BLKSTR,
	*snakeoil_REGSTR,
	*snakeoil_FIFOSTR,
	*snakeoil_LNKSTR,
	*snakeoil_SOCKSTR,
	*snakeoil_UNKNOWNSTR;

/* This function does the actual work for listdir_files and listdir_dirs. */

static PyObject*
snakeoil_readdir_actual_listdir(const char* path, int followsyms,
	int dkind, int skind)
{
	DIR *the_dir;
	struct dirent *entry;

	PyObject *string;

	int pathlen = strlen(path);

	PyObject *result = PyList_New(0);
	if (!result) {
		return NULL;
	}
	if (!(the_dir = opendir(path))) {
		return PyErr_SetFromErrno(PyExc_OSError);
	}
	errno = 0;
	while (entry = readdir(the_dir)) {
		const char *name = entry->d_name;
		/* skip over "." and ".." */
		if (name[0] == '.' && (name[1] == 0 || (name[1] == '.' &&
			name[2] == 0))) {
			continue;
		}
#ifdef HAVE_DIRENT_D_TYPE
		if (entry->d_type == DT_UNKNOWN ||
			(followsyms && entry->d_type == DT_LNK))
#endif /*HAVE_DIRENT_D_TYPE*/
		{

			/* both path components, the "/", the trailing null */

			size_t size = pathlen + strlen(name) + 2;
			char *buffer = (char *) malloc(size);
			if (!buffer) {
				Py_DECREF(result);
				return PyErr_NoMemory();
			}
			snprintf(buffer, size, "%s/%s", path, name);

			struct stat st;
			int ret;
			if (followsyms) {
				ret = stat(buffer, &st);
			} else {
				ret = lstat(buffer, &st);
			}
			free(buffer);
			if (ret != 0) {
				if (followsyms && errno == ENOENT) {
					/* hit a dangling symlink; skip. */
					errno = 0;
					continue;
				}
				Py_DECREF(result);
				result = NULL;
				break;
			}

			if ((st.st_mode & S_IFMT) != skind) {
				continue;
			}
		}
#ifdef HAVE_DIRENT_D_TYPE
		else if (entry->d_type != dkind) {
			continue;
		}
#endif /*HAVE_DIRENT_D_TYPE*/
		if (!(string = PyString_FromString(name))) {
			Py_DECREF(result);
			result = NULL;
			break;
		}
		if (PyList_Append(result, string) == -1) {
			Py_DECREF(string);
			Py_DECREF(result);
			result = NULL;
			break;
		}
		Py_DECREF(string);
	}
	closedir(the_dir);
	if (errno) {
		return PyErr_SetFromErrno(PyExc_OSError);
	}
	return result;
}

static PyObject*
snakeoil_readdir_listdir_dirs(PyObject* self, PyObject* args)
{
	char *path;
	PyObject *follow_symlinks_obj = Py_True;

	if (!PyArg_ParseTuple(args, "s|O", &path, &follow_symlinks_obj)) {
		return NULL;
	}

	int follow_symlinks = PyObject_IsTrue(follow_symlinks_obj);
	if (follow_symlinks == -1) {
		return NULL;
	}

	return snakeoil_readdir_actual_listdir(path, follow_symlinks,
		DT_DIR, S_IFDIR);
}

static PyObject*
snakeoil_readdir_listdir_files(PyObject* self, PyObject* args)
{
	char *path;
	PyObject *follow_symlinks_obj = Py_True;

	if (!PyArg_ParseTuple(args, "s|O", &path, &follow_symlinks_obj)) {
		return NULL;
	}

	int follow_symlinks = PyObject_IsTrue(follow_symlinks_obj);
	if (follow_symlinks == -1) {
		return NULL;
	}

	return snakeoil_readdir_actual_listdir(path, follow_symlinks,
		DT_REG, S_IFREG);
}

static PyObject*
snakeoil_readdir_listdir(PyObject* self, PyObject* args)
{
	char *path;

	if (!PyArg_ParseTuple(args, "s", &path)) {
		return NULL;
	}

	PyObject *result = PyList_New(0);
	if (!result) {
		return NULL;
	}

	DIR *the_dir = opendir(path);
	if (!the_dir) {
		return PyErr_SetFromErrno(PyExc_OSError);
	}
	errno = 0;
	struct dirent *entry;
	while (entry = readdir(the_dir)) {
		const char *name = entry->d_name;
		/* skip over "." and ".." */
		if (!(name[0] == '.' && (name[1] == 0 ||
			(name[1] == '.' && name[2] == 0)))) {

			PyObject *string = PyString_FromString(name);
			if (!string) {
				Py_DECREF(result);
				result = NULL;
				break;
			}
			int res = PyList_Append(result, string);
			Py_DECREF(string);
			if (res == -1) {
				Py_DECREF(result);
				result = NULL;
				break;
			}
		}
	}
	closedir(the_dir);
	if (errno) {
		return PyErr_SetFromErrno(PyExc_OSError);
	}
	return result;
}

static PyObject*
snakeoil_readdir_read_dir(PyObject* self, PyObject* args)
{
	char *path;

	if (!PyArg_ParseTuple(args, "s", &path)) {
		return NULL;
	}
	ssize_t pathlen = strlen(path);

	PyObject *result = PyList_New(0);
	if (!result) {
		return NULL;
	}

	DIR *the_dir = opendir(path);
	if (!the_dir) {
		return PyErr_SetFromErrno(PyExc_OSError);
	}

	struct dirent *entry;
	while (entry = readdir(the_dir)) {
		const char *name = entry->d_name;
		/* skip over "." and ".." */
		if (name[0] == '.' && (name[1] == 0 ||
			(name[1] == '.' && name[2] == 0))) {
			continue;
		}

		PyObject *typestr;
#ifdef HAVE_DIRENT_D_TYPE
		switch (entry->d_type) {
			case DT_REG:
				typestr = snakeoil_REGSTR;
				break;
			case DT_DIR:
				typestr = snakeoil_DIRSTR;
				break;
			case DT_FIFO:
				typestr = snakeoil_FIFOSTR;
				break;
			case DT_SOCK:
				typestr = snakeoil_SOCKSTR;
				break;
			case DT_CHR:
				typestr = snakeoil_CHRSTR;
				break;
			case DT_BLK:
				typestr = snakeoil_BLKSTR;
				break;
			case DT_LNK:
				typestr = snakeoil_LNKSTR;
				break;
			case DT_UNKNOWN:
#endif /*HAVE_DIRENT_D_TYPE*/
			{
				/* both path components, the "/", the trailing null */
				size_t size = pathlen + strlen(name) + 2;
				char *buffer = (char *) malloc(size);
				if (!buffer) {
					closedir(the_dir);
					return PyErr_NoMemory();
				}
				snprintf(buffer, size, "%s/%s", path, name);
				struct stat st;
				int ret = lstat(buffer, &st);
				free(buffer);
				if (ret == -1) {
					closedir(the_dir);
					return PyErr_SetFromErrno(PyExc_OSError);
				}
				switch (st.st_mode & S_IFMT) {
					case S_IFDIR:
						typestr = snakeoil_DIRSTR;
						break;
					case S_IFCHR:
						typestr = snakeoil_CHRSTR;
						break;
					case S_IFBLK:
						typestr = snakeoil_BLKSTR;
						break;
					case S_IFREG:
						typestr = snakeoil_REGSTR;
						break;
					case S_IFLNK:
						typestr = snakeoil_LNKSTR;
						break;
					case S_IFSOCK:
						typestr = snakeoil_SOCKSTR;
						break;
					case S_IFIFO:
						typestr = snakeoil_FIFOSTR;
						break;
					default:
						/* XXX does this make sense? probably not. */
						typestr = snakeoil_UNKNOWNSTR;
				}
			}
#ifdef HAVE_DIRENT_D_TYPE
			break;

			default:
				/* XXX does this make sense? probably not. */
				typestr = snakeoil_UNKNOWNSTR;
		}
#endif /*HAVE_DIRENT_D_TYPE*/

		PyObject *namestr = PyString_FromString(name);
		if (!namestr) {
			Py_DECREF(result);
			result = NULL;
			break;
		}
		/* Slight hack: incref typestr after our error checks. */
		PyObject *tuple = PyTuple_Pack(2, namestr, typestr);
		Py_DECREF(namestr);
		if (!tuple) {
			Py_DECREF(result);
			result = NULL;
			break;
		}
		Py_INCREF(typestr);

		int res = PyList_Append(result, tuple);
		Py_DECREF(tuple);
		if (res == -1) {
			Py_DECREF(result);
			result = NULL;
			break;
		}
	}
	if (closedir(the_dir) == -1) {
		return PyErr_SetFromErrno(PyExc_OSError);
	}
	return result;
}

/* Module initialization */

static PyMethodDef snakeoil_readdir_methods[] = {
	{"listdir", (PyCFunction)snakeoil_readdir_listdir, METH_VARARGS,
	 "listdir(path, followSymlinks=True, kinds=everything)"},
	{"listdir_dirs", (PyCFunction)snakeoil_readdir_listdir_dirs, METH_VARARGS,
	 "listdir_dirs(path, followSymlinks=True)"},
	{"listdir_files", (PyCFunction)snakeoil_readdir_listdir_files, METH_VARARGS,
	 "listdir_files(path, followSymlinks=True)"},
	{"readdir", (PyCFunction)snakeoil_readdir_read_dir, METH_VARARGS,
	 "read_dir(path)"},
	{NULL}
};

PyDoc_STRVAR(
	snakeoil_module_documentation,
	"C reimplementation of some of snakeoil.osutils");

PyMODINIT_FUNC
init_readdir(void)
{
	PyObject *m;

	/* XXX we have to initialize these before we call InitModule3 because
	 * the snakeoil_readdir_methods use them, which screws up error handling.
	 */
	snakeoil_LOAD_STRING(snakeoil_DIRSTR, "directory");
	snakeoil_LOAD_STRING(snakeoil_CHRSTR, "chardev");
	snakeoil_LOAD_STRING(snakeoil_BLKSTR, "block");
	snakeoil_LOAD_STRING(snakeoil_REGSTR, "file");
	snakeoil_LOAD_STRING(snakeoil_FIFOSTR, "fifo");
	snakeoil_LOAD_STRING(snakeoil_LNKSTR, "symlink");
	snakeoil_LOAD_STRING(snakeoil_SOCKSTR, "socket");
	snakeoil_LOAD_STRING(snakeoil_UNKNOWNSTR, "unknown");

	/* Create the module and add the functions */
	m = Py_InitModule3("_readdir", snakeoil_readdir_methods,
					   snakeoil_module_documentation);
	if (!m)
		return;

	/* Success! */
}
