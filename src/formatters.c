/*
 Copyright: 2007-2010 Charlie Shepherd <masterdriverz@gentoo.org>
 Copyright: 2009-2011 Brian Harring <ferringb@gmail.com>
 License: BSD/GPL2
*/

#include "snakeoil/common.h"
#include "structmember.h"

/*
 * Known bugs:
 *   encoding isn't modifiable after the fact.  should be.
 * optimizations:
 *   PyUnicode_Find internally makes its own objs when doing subranges- inline the lookup.
 *   currently creates 2n strings on slicing; leftbit, remaining- use windowing instead, just
 *   pullng the window as needed.
 */


#define RETURN_POSSIBLE_NONE(target) \
{  \
	if (!(target)) { \
		Py_RETURN_NONE; \
	} \
	Py_INCREF((target)); \
	return (target); \
}

#define SWAP_VALUE_HANDLE_NULL(target, newval) \
{  \
	PyObject *tmp = (target); \
	Py_INCREF((newval)); \
	(target) = (newval); \
	Py_XDECREF(tmp); \
}


/* Duplicating this is annoying, but we need to
   access it from the C level, so we do. */
static PyObject *StreamClosed = NULL;
static PyObject *PTF_unic_space = NULL;

/* PlainTextFormatter is abbreviated to PTF */

typedef struct {
	PyObject_HEAD

	/* This is actually the write method of stream if it's not a file */
	PyObject *stream_callable;
	PyObject *first_prefix;
	PyObject *later_prefix;

	/* need these for TermInfoFormatter */

	PyObject *reset;
	PyObject *bold;
	PyObject *underline;
	PyObject *encoding;
	int width;
	int autoline;
	int wrap;

	PyObject *raw_stream;
	int pos;
	int in_first_line;
	int wrote_something;

} PTF_object;

snakeoil_MUTABLE_ATTR_BOOL(PTF_object, "autoline", autoline, self->autoline,
	self->autoline = 1, self->autoline = 0)
snakeoil_MUTABLE_ATTR_BOOL(PTF_object, "wrap", wrap, self->wrap,
	self->wrap = 1, self->wrap = 0)
snakeoil_GET_ATTR(PTF_object, "first_prefix", first_prefix, self->first_prefix)
snakeoil_GET_ATTR(PTF_object, "later_prefix", later_prefix, self->later_prefix)


static int
PTF_set_first_prefix(PTF_object *self, PyObject *value, void *closure)
{
	PyObject *tmp;
	if (!value) {
		PyErr_SetString(PyExc_TypeError, "first_prefix is not deletable");
		return -1;
	}

	if (!PyList_CheckExact(value))
		return PyList_SetSlice(self->first_prefix,
			0, PyList_GET_SIZE(self->first_prefix),
			value);

	SWAP_VALUE_HANDLE_NULL(self->first_prefix, value);
	return 0;
}

static int
PTF_set_later_prefix(PTF_object *self, PyObject *value, void *closure)
{
	PyObject *tmp;
	if (!value) {
		PyErr_SetString(PyExc_TypeError, "later_prefix is not deletable");
		return -1;
	}

	if (!PyList_CheckExact(value))
		return PyList_SetSlice(self->later_prefix,
			0, PyList_GET_SIZE(self->later_prefix),
			value);

	SWAP_VALUE_HANDLE_NULL(self->later_prefix, value);
	return 0;
}

static PyObject *
PTF_getstream(PTF_object *self, void *closure)
{
	RETURN_POSSIBLE_NONE(self->raw_stream);
}

static int
PTF_set_encoding(PTF_object *self, PyObject *value, void *closure)
{
	PyObject *tmp;
	if (!value) {
		PyErr_SetString(PyExc_TypeError, "encoding prefix is not deletable");
		return -1;
	} else if (!PyString_CheckExact(value)) {
		PyErr_SetString(PyExc_TypeError, "encoding must be a string");
		return -1;
	}
	SWAP_VALUE_HANDLE_NULL(self->encoding, value);
	return 0;
}

static PyObject *
PTF_get_encoding(PTF_object *self, void *closure)
{
	PyObject *tmp = self->encoding;
	if (!tmp) {
		PyErr_SetString(PyExc_RuntimeError, "PTF instance has null encoding; this shouldn't be possible");
		return tmp;
	}
	Py_INCREF(tmp);
	return tmp;
}

static int
PTF_setstream(PTF_object *self, PyObject *value, void *closure)
{
	PyObject *tmp;
	if (value == NULL) {
		PyErr_SetString(PyExc_TypeError, "Cannot delete the stream attribute");
		return -1;
	}

	if (PyFile_Check(value)) {
		Py_CLEAR(self->stream_callable);
	} else {
		tmp = PyObject_GetAttrString(value, "write");
		if (!tmp) {
			return -1;
		}
		PyObject *tmp2 = self->stream_callable;
		self->stream_callable = tmp;
		Py_XDECREF(tmp2);
	}

	SWAP_VALUE_HANDLE_NULL(self->raw_stream, value);
	return 0;
}


static int
PTF_traverse(PTF_object *self, visitproc visit, void *arg)
{
	Py_VISIT(self->stream_callable);
	Py_VISIT(self->raw_stream);
	Py_VISIT(self->first_prefix);
	Py_VISIT(self->later_prefix);
	Py_VISIT(self->reset);
	Py_VISIT(self->bold);
	Py_VISIT(self->underline);
	Py_VISIT(self->encoding);
	return 0;
}

static int
PTF_clear(PTF_object *self)
{
	Py_CLEAR(self->stream_callable);
	Py_CLEAR(self->raw_stream);
	Py_CLEAR(self->first_prefix);
	Py_CLEAR(self->later_prefix);
	Py_CLEAR(self->reset);
	Py_CLEAR(self->bold);
	Py_CLEAR(self->underline);
	Py_CLEAR(self->encoding);
	return 0;
}

static void
PTF_dealloc(PTF_object *self) {
	PTF_clear(self);
	self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
PTF_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	PTF_object *self;
	PyObject *encoding;
	if (!(encoding = PyString_FromString("ascii")))
		return NULL;
	self = (PTF_object *)type->tp_alloc(type, 0);
	if (!self) {
		Py_DECREF(encoding);
		return NULL;
	}

	self->autoline = self->in_first_line = 1;
	self->pos = self->wrap = self->wrote_something = 0;
	self->encoding = encoding;
	self->first_prefix = self->later_prefix = self->bold = self->reset = self->underline = NULL;
	self->raw_stream = self->stream_callable = NULL;

	self->width = 79;
	 /* this should pick up on the system default but i'm lazy. */
	if (!(self->first_prefix = PyList_New(0))) {
		Py_DECREF(self);
		return NULL;
	}
	if (!(self->later_prefix = PyList_New(0))) {
		Py_DECREF(self);
		return NULL;
	}
	if (!(self->bold = PyString_FromString(""))) {
		Py_DECREF(self);
		return NULL;
	}
	Py_INCREF(self->bold);
	self->reset = self->bold;
	Py_INCREF(self->bold);
	self->underline = self->bold;
	return (PyObject *)self;
}

static int
PTF_init(PTF_object *self, PyObject *args, PyObject *kwds)
{
	PyObject *encoding = NULL, *tmp, *stream = NULL;
	int width = 0;
	static char *kwlist[] = {"stream", "width", "encoding", NULL};

	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|iO", kwlist,
		&stream, &width, &encoding))
		return -1;

	if (encoding == Py_None)
		encoding = NULL;

	if (encoding) {
		if (!PyString_Check(encoding)) {
			PyErr_SetString(PyExc_TypeError,
				"encoding must be None, or a str object");
			return -1;
		}
		tmp = self->encoding;
		Py_INCREF(encoding);
		self->encoding = encoding;
		Py_XDECREF(tmp);
	} else {
		/* try to pull it from the stream, else from the current settings */
		if (!(encoding = PyObject_GetAttrString(stream, "encoding"))) {
			PyErr_Clear();
		} else if (!PyString_Check(encoding)) {
			Py_CLEAR(encoding);
		}
		if (!encoding) {
			/* try system setting */
			const char *p = PyUnicode_GetDefaultEncoding();
			if (!p) {
				/* should check for locale error here instead of just wiping... */
				PyErr_Clear();
			} else if (!(encoding = PyString_FromString(p))) {
				/* can't do dick here. */
				return -1;
			}
		}
		if (encoding) {
			tmp = self->encoding;
			self->encoding = encoding;
			Py_DECREF(tmp);
		}
	}
	if (width > 0)
		self->width = width;

	return PTF_setstream(self, stream, NULL);
}

/*
 * repeatedly reduce a callable invoking func(self), till it's no longer callable
 * steals the passed in ref, and returns a new reference.
 */
static PyObject *
reduce_callable(PTF_object *self, PyObject *arg)
{
	PyObject *tmp;
	while (PyCallable_Check(arg)) {
		tmp = PyObject_CallFunctionObjArgs(arg, (PyObject *)self, NULL);
		if (!tmp)
			return tmp;
		Py_DECREF(arg);
		arg = tmp;
	}
	return arg;
}

static int
_flush_newline(PTF_object *self)
{
	PyObject *tmp;
	if (self->stream_callable) {
		tmp = PyObject_CallFunction(self->stream_callable, "(s)", "\n");
		if (!tmp)
			return -1;
		Py_DECREF(tmp);
	} else {
		if (PyFile_WriteString("\n", self->raw_stream))
			return -1;
	}
	self->wrote_something = 0;
	self->pos = 0;
	return 0;
}

/* convert passed in object, stealing the reference, returning a new reference
 * for the encoded version, else NULL with exception set
 */
static inline PyObject *
PTF_convert_encoding(PTF_object *self, PyObject *data)
{
	PyObject *tmp;
	tmp = PyUnicode_AsEncodedString(data, PyString_AS_STRING(self->encoding),
		"replace");
	Py_DECREF(data);
	return tmp;
}

static int
_write_prefix(PTF_object *self, int wrap) {
	PyObject *iter, *arg, *tmp;
	Py_ssize_t len;
	int ret;

	iter = self->in_first_line ? self->first_prefix : self->later_prefix;
	if (!(iter = PyObject_GetIter(iter)))
		return -1;

	while (arg = PyIter_Next(iter)) {
		if (!(arg = reduce_callable(self, arg))) {
			Py_DECREF(iter);
			return -1;
		}

		if (arg == Py_None) {
			Py_DECREF(arg);
			continue;
		}

		if (!PyString_Check(arg)) {
			int is_unicode = PyUnicode_Check(arg);
			if (!is_unicode) {
				tmp = PyObject_Str(arg);
				Py_DECREF(arg);
				if (!tmp) {
					Py_DECREF(iter);
					return -1;
				}
				is_unicode = PyUnicode_Check(arg);
			}
			if (is_unicode) {
				len = PyUnicode_GET_SIZE(arg);
				if (!(arg = PTF_convert_encoding(self, arg))) {
					Py_DECREF(iter);
					return -1;
				}
			} else {
				if (!(len = PyObject_Length(arg))) {
					Py_DECREF(iter);
					Py_DECREF(arg);
					return -1;
				}
			}
		} else {
			len = PyString_GET_SIZE(arg);
		}

		if (self->stream_callable) {
			tmp = PyObject_CallFunctionObjArgs(self->stream_callable, arg, NULL);
			Py_XDECREF(tmp);
			ret = tmp == NULL;
		} else {
			ret = PyFile_WriteObject(arg, self->raw_stream, Py_PRINT_RAW);
		}
		Py_DECREF(arg);
		if (ret) {
			Py_DECREF(iter);
			return -1;
		}
		// overflow potential.
		self->pos += len;
	}
	if (wrap && (self->pos >= self->width))
		self->pos = self->width-10;
	Py_DECREF(iter);
	return 0;
}

static PyObject *
PTF_write(PTF_object *self, PyObject *args, PyObject *kwargs) {
	PyObject *wrap=NULL, *autoline=NULL, *prefixes=NULL, *prefix=NULL;
	PyObject *first_prefixes=NULL, *later_prefixes=NULL;
	PyObject *first_prefix=NULL, *later_prefix=NULL;
	PyObject *tmp=NULL, *arg=NULL;
	PyObject *iterator=NULL, *e=NULL;

	int maxlen, space, failed = 1;
	int i_wrap = self->wrap;
	int i_autoline = self->autoline;
	Py_ssize_t first_prune = 0, later_prune = 0;
	Py_ssize_t arg_len = 0;

#define getitem(ptr) ptr = PyDict_GetItemString(kwargs, #ptr);

	if (kwargs) {
		getitem(prefix);
		getitem(first_prefix);
		getitem(later_prefix);
		getitem(prefixes);
		getitem(first_prefixes);
		getitem(later_prefixes);
		getitem(wrap);
		getitem(autoline);
	}
#undef getitem

	if (autoline) {
		if (-1 == (i_autoline = PyObject_IsTrue(autoline))) {
			return NULL;
		}
	}

	if (wrap) {
		if (-1 == (i_wrap = PyObject_IsTrue(wrap))) {
			return NULL;
		}
	}

	if (prefixes) {
		if (first_prefixes || later_prefixes) {
			PyErr_SetString(PyExc_TypeError,
				"do not pass first_prefixes or later_prefixes "
				"if prefixes is passed");
			return NULL;
		}
		first_prefixes = later_prefixes = prefixes;
	}

	if (prefix) {
		if (first_prefix || later_prefix) {
			PyErr_SetString(PyExc_TypeError,
				"do not pass first_prefix or later_prefix with prefix");
			return NULL;
		}
		first_prefix = later_prefix = prefix;
	}

	if (first_prefix) {
		if (first_prefixes) {
			PyErr_SetString(PyExc_TypeError,
				"do not pass both first_prefix and first_prefixes");
			return NULL;
		}
		if (PyList_Append(self->first_prefix, first_prefix))
			return NULL;
		first_prune = 1;
	} else if (first_prefixes) {
		first_prune = PyList_GET_SIZE(self->first_prefix);
		if (!(tmp = _PyList_Extend((PyListObject *)self->first_prefix, first_prefixes)))
			return NULL;
		Py_DECREF(tmp);
		first_prune = PyList_GET_SIZE(self->first_prefix) - first_prune;
	}

	if (later_prefix) {
		if (later_prefixes) {
			PyErr_SetString(PyExc_TypeError,
				"do not pass both later_prefix and later_prefixes");
			goto finally;
		}
		if (PyList_Append(self->later_prefix, later_prefix))
			goto finally;
		later_prune = 1;
	} else if (later_prefixes) {
		later_prune = PyList_GET_SIZE(self->later_prefix);
		if (!(tmp = _PyList_Extend((PyListObject *)self->later_prefix, later_prefixes))) {
			later_prune = 0;
			goto finally;
		}
		Py_DECREF(tmp);
		later_prune = PyList_GET_SIZE(self->later_prefix) - later_prune;
	}

	if (!(iterator = PyObject_GetIter(args)))
		goto finally;

	while (arg = PyIter_Next(iterator)) {
		/* If we're at the start of the line, write our prefix.
		 * There is a deficiency here: if neither our arg nor our
		 * prefix affect _pos (both are escape sequences or empty)
		 * we will write prefix more than once. This should not
		 * matter.
		 */

		int is_unicode;
		if (self->pos == 0)
			if (_write_prefix(self, i_wrap))
				goto finally;

		if (!(arg = reduce_callable(self, arg)))
			goto finally;

		if (arg == Py_None) {
			Py_CLEAR(arg);
			continue;
		}

		if (!PyString_Check(arg)) {
			is_unicode = PyUnicode_Check(arg);
			if (!is_unicode) {
				tmp = PyObject_Str(arg);
				Py_CLEAR(arg);
				if (!tmp)
					goto finally;
				arg = tmp;
				is_unicode = PyUnicode_Check(arg);
			}
			if (is_unicode) {
				arg_len = PyUnicode_GET_SIZE(arg);
			} else {
				if (!(arg_len = PyObject_Length(arg)))
					goto finally;
			}
		} else {
			arg_len = PyString_GET_SIZE(arg);
			is_unicode = 0;
		}

		if (!arg_len) {
			/* There's nothing to write, so skip this bit... */
			Py_CLEAR(arg);
			continue;
		}

		while (i_wrap && (arg_len > self->width - self->pos)) {
			PyObject *bit = NULL;
			/* We have to split. */
			maxlen = self->width - self->pos;
			// this should be wiped; it's added for the moment since I'm
			// not so sure about the code flow following for when
			// arg_len == max_len
			int tmp_max = arg_len > maxlen ? maxlen : arg_len;
			if (is_unicode) {
				if (-2 == (space = PyUnicode_Find(arg, PTF_unic_space, 0, tmp_max, -1)))
					goto finally;
			} else {
				char *start, *p;
				start = PyString_AS_STRING(arg);
				p = start + tmp_max - 1;
				while (p >= start && ' ' != *p)
					p--;
				space = start > p ? -1 : p - start;
			}

			if (space == -1) {
				/* No space to split on.

				 * If we are on the first line we can simply go to
				 * the next (this helps if the "later" prefix is
				 * shorter and should not really matter if not).

				 * If we are on the second line and have already
				 * written something we can also go to the next
				 * line.
				 */

				if (self->in_first_line || self->wrote_something) {
					if (!(bit = PyString_FromString(""))) {
						goto finally;
					}
				} else {
					/* Forcibly split this as far to the right as
					 * possible.
					 */
					if (!(bit = PySequence_GetSlice(arg, 0, tmp_max)))
						goto finally;
					tmp = PySequence_GetSlice(arg, tmp_max, arg_len);
					Py_CLEAR(arg);
					if (!tmp) {
						Py_DECREF(bit);
						goto finally;
					}
					arg_len -= tmp_max;
					arg = tmp;
				}
			} else {
				/* Omit the space we split on.*/
				if (!(bit = PySequence_GetSlice(arg, 0, space)))
					goto finally;
				tmp = PySequence_GetSlice(arg, space+1, arg_len);
				Py_CLEAR(arg);
				if (!tmp) {
					Py_DECREF(bit);
					goto finally;
				}
				arg_len -= space + 1;
				arg = tmp;
			}

			if (is_unicode && !(bit = PTF_convert_encoding(self, bit)))
				goto finally;

			int ret = 0;
			if (self->stream_callable) {
				tmp = PyObject_CallFunctionObjArgs(self->stream_callable, bit, NULL);
				Py_XDECREF(tmp);
				ret = tmp == NULL;
			} else {
				ret = PyFile_WriteObject(bit, self->raw_stream, Py_PRINT_RAW);
			}
			Py_DECREF(bit);
			if (ret)
				goto finally;
			if (_flush_newline(self))
				goto finally;

			self->in_first_line = 0;
			if (_write_prefix(self, i_wrap))
				goto finally;

		}

		if (is_unicode && !(arg = PTF_convert_encoding(self, arg)))
			goto finally;
		if (self->stream_callable) {
			tmp = PyObject_CallFunctionObjArgs(self->stream_callable, arg, NULL);
			Py_XDECREF(tmp);
			if (!tmp) {
				goto finally;
			}
		} else {
			if (PyFile_WriteObject(arg, self->raw_stream, Py_PRINT_RAW)) {
				goto finally;
			}
		}
		self->pos += arg_len;
		self->wrote_something = 1;
		Py_CLEAR(arg);
	}

	if (i_autoline) {
		if (_flush_newline(self))
			goto finally;
		self->in_first_line = 1;
	}

	failed = 0;

finally:
	Py_XDECREF(iterator);
	Py_XDECREF(arg);

	if (first_prune) {
		PyList_SetSlice(self->first_prefix, -first_prune, PyList_GET_SIZE(self->first_prefix), NULL);
	}
	if (later_prune) {
		PyList_SetSlice(self->later_prefix, -later_prune, PyList_GET_SIZE(self->later_prefix), NULL);
	}

	e = PyErr_Occurred();
	if (e) {
		if (PyErr_ExceptionMatches(PyExc_IOError) &&
			PyInt_AS_LONG(PyObject_GetAttrString(e, "errno")) == EPIPE)
				PyErr_SetObject(e, StreamClosed);
		return NULL;
	}

	if (failed)
		return NULL;
	Py_RETURN_NONE;
}

PyDoc_STRVAR(
	PTF_write_doc,
"Write something to the stream.\n\
\n\
Acceptable arguments are:\n\n\
* Strings are simply written to the stream.\n\
* None is ignored.\n\
* Functions are called with the formatter as argument.\n\
  Their return value is then used the same way as the other\n\
  arguments.\n\
* Formatter subclasses might special-case certain objects.\n\
\n\
Accepts wrap and autoline as keyword arguments. Effect is\n\
the same as setting them before the write call and resetting\n\
them afterwards.\n\
\n\
Accepts first_prefixes and later_prefixes as keyword\n\
arguments. They should be sequences that are temporarily\n\
appended to the first_prefix and later_prefix attributes.\n\
\n\
Accepts prefixes as a keyword argument. Effect is the same as\n\
setting first_prefixes and later_prefixes to the same value.\n\
\n\
Accepts first_prefix, later_prefix and prefix as keyword\n\
argument. Effect is the same as setting first_prefixes,\n\
later_prefixes or prefixes to a one-element tuple.\n\
\n\
The formatter has a couple of attributes that are useful as arguments\n\
to write.");

static PyMethodDef PTF_methods[] = {
	{"write", (PyCFunction)PTF_write, METH_VARARGS | METH_KEYWORDS,
		PTF_write_doc
	},
	{NULL}  /* Sentinel */
};

static PyGetSetDef PTF_getseters[] = {
	{"autoline", (getter)PTF_object_get_autoline,
		(setter)PTF_object_set_autoline,
		"boolean indicating we are in auto-newline mode "
		"(defaults to on).", NULL},
	{"wrap", (getter)PTF_object_get_wrap, (setter)PTF_object_set_wrap,
		"boolean indicating we auto-linewrap (defaults to off).", NULL},
	{"stream", (getter)PTF_getstream, (setter)PTF_setstream,
		"stream to write to",NULL},
	{"first_prefix", (getter)PTF_object_get_first_prefix,
		(setter)PTF_set_first_prefix,
		"a list of items to write on the first line.", NULL},
	{"later_prefix", (getter)PTF_object_get_later_prefix,
		(setter)PTF_set_later_prefix,
		"a list of items to write on every line but the first.", NULL},
	{"encoding", (getter)PTF_get_encoding, (setter)PTF_set_encoding,
		"encoding", NULL},
	{NULL} /* Sentinel */
};

#undef pyobj_struct

static PyMemberDef PTF_members[] = {
	{"width", T_INT, offsetof(PTF_object, width), 0,
		 "width to split at"},
	{"_pos", T_INT, offsetof(PTF_object, pos), 0,
		 "current position"},
	{"bold", T_OBJECT_EX, offsetof(PTF_object, bold), 0,
		"object to use to get 'bold' semantics"},
	{"reset", T_OBJECT_EX, offsetof(PTF_object, reset), 0,
		"object to use to get 'reset' semantics"},
	{"underline", T_OBJECT_EX, offsetof(PTF_object, underline), 0,
		"object to use to get 'underline' semantics"},
	{NULL}  /* Sentinel */
};


static PyTypeObject PTF_type = {
		PyObject_HEAD_INIT(NULL)
		0,							  /* ob_size */
		"formatters.PlainTextFormatter",/* tp_name */
		sizeof(PTF_object),			 /* tp_basicsize */
		0,							  /* tp_itemsize */
		(destructor)PTF_dealloc,		/* tp_dealloc */
		0,							  /* tp_print */
		0,							  /* tp_getattr */
		0,							  /* tp_setattr */
		0,							  /* tp_compare */
		0,							  /* tp_repr */
		0,							  /* tp_as_number */
		0,							  /* tp_as_sequence */
		0,							  /* tp_as_mapping */
		0,							  /* tp_hash */
		0,							  /* tp_call */
		0,							  /* tp_str */
		0,							  /* tp_getattro */
		0,							  /* tp_setattro */
		0,							  /* tp_as_buffer */
		Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_CLASS | Py_TPFLAGS_BASETYPE | Py_TPFLAGS_HAVE_GC,	/* tp_flags */
		0,							  /* tp_doc */
		(traverseproc)PTF_traverse,	 /* tp_traverse */
		(inquiry)PTF_clear,			 /* tp_clear */
		0,							  /* tp_richcompare */
		0,							  /* tp_weaklistoffset */
		0,							  /* tp_iter */
		0,							  /* tp_iternext */
		PTF_methods,					/* tp_methods */
		PTF_members,					/* tp_members */
		PTF_getseters,				  /* tp_getset */
		0,							  /* tp_base */
		0,							  /* tp_dict */
		0,							  /* tp_descr_get */
		0,							  /* tp_descr_set */
		0,							  /* tp_dictoffset */
		(initproc)PTF_init,			 /* tp_init */
		0,							  /* tp_alloc */
		PTF_new,						/* tp_new */
};

PyDoc_STRVAR(
	formatters_module_doc,
	"C implementation of snakeoil.formatters.PlainTextFormatter.\n");

PyMODINIT_FUNC
init_formatters(void)
{
	PyObject *tmp;
	PyObject *m = Py_InitModule3("_formatters", NULL, formatters_module_doc);
	if (!m)
		return;

	if (!StreamClosed) {
		if (!(StreamClosed = PyErr_NewException("snakeoil._formatters.StreamClosed",
			PyExc_KeyboardInterrupt, NULL)))
			return;
	}
	Py_INCREF(StreamClosed);
	if (PyModule_AddObject(m, "StreamClosed", StreamClosed))
		return;

	if (!PTF_unic_space) {
		if (!(tmp = PyString_FromString(" ")))
			return;
		PTF_unic_space = PyUnicode_FromObject(tmp);
		Py_DECREF(tmp);
		if (!PTF_unic_space)
			return;
	}

	if (PyType_Ready(&PTF_type) < 0)
		return;
	Py_INCREF(&PTF_type);
	if (PyModule_AddObject(m, "PlainTextFormatter", (PyObject *)&PTF_type) == -1)
		return;
}
