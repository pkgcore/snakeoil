#include "Python.h"
#include <snakeoil/common.h>
#include "structmember.h"

/*
 * Known bugs:
 *      - Passing Unicode objects that cannot be
 *        decoded by the encoding to write causes an
 *        EncodingError to be raised, even though we
 *        use "replace". :-\
 */



/* Duplicating this is annoying, but we need to
   access it from the C level, so we do. */
static PyObject *StreamClosed;

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

#define annoying_pyobj_func(name, attr) pyobj_get_func(name, attr) \
    pyobj_set_func(name, attr)

#define pyobj_get_func(name, attr) static PyObject *               \
PTF_getobj_##name(PTF_object *self, void *closure)                 \
{                                                                  \
    Py_INCREF(self->attr);                                         \
    return self->attr;                                             \
}                                                                  \

#define pyobj_set_func(name, attr) static int                      \
PTF_setobj_##name(PTF_object *self, PyObject *value, void *closure)\
{                                                                  \
    if (value == NULL) {                                           \
        PyErr_SetString(PyExc_TypeError,                           \
                "Cannot delete the "#name" attribute");            \
        return -1;                                                 \
    }                                                              \
    Py_DECREF(self->attr);                                         \
    Py_INCREF(value);                                              \
    self->attr = value;                                            \
    return 0;                                                      \
}

#define pyobj_func(name) annoying_pyobj_func(name, name)

pyobj_func(bold)
pyobj_func(underline)
pyobj_func(reset)

snakeoil_MUTABLE_ATTR_BOOL(PTF_object, "autoline", autoline, self->autoline,
    self->autoline = 1, self->autoline = 0)
snakeoil_GET_ATTR(PTF_object, "first_prefix", first_prefix, self->first_prefix)
snakeoil_GET_ATTR(PTF_object, "later_prefix", later_prefix, self->later_prefix)


static int
PTF_set_first_prefix(PTF_object *self, PyObject *value, void *closure)
{
    PyObject *tmp;
    if(!value) {
        PyErr_SetString(PyExc_TypeError, "first_prefix is not deletable");
        return -1;
    }
        
    if(!PyList_CheckExact(self->first_prefix))
        return PyList_SetSlice(self->first_prefix,
            0, PyList_GET_SIZE(self->first_prefix),
            value);
    tmp = self->first_prefix;
    Py_INCREF(value);
    self->first_prefix = value;
    Py_DECREF(tmp);
    return 0;
}

static int
PTF_set_later_prefix(PTF_object *self, PyObject *value, void *closure)
{
    PyObject *tmp;
    if(!value) {
        PyErr_SetString(PyExc_TypeError, "later_prefix is not deletable");
        return -1;
    }
        
    if(!PyList_CheckExact(self->later_prefix))
        return PyList_SetSlice(self->later_prefix,
            0, PyList_GET_SIZE(self->later_prefix),
            value);
    tmp = self->later_prefix;
    Py_INCREF(value);
    self->later_prefix = value;
    Py_DECREF(tmp);
    return 0;
}

static PyObject *
PTF_returnemptystring(PTF_object *self, PyObject *args)
{
    char *s;
    if (!PyArg_ParseTuple(args, "|s", s))
        return NULL;

    return PyString_FromString("");
}


static PyObject *
PTF_getstream(PTF_object *self, void *closure)
{
    Py_INCREF(self->raw_stream);
    return self->raw_stream;
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
            if (!PyErr_Occurred())
                PyErr_SetString(PyExc_TypeError, "stream has no write method");
            return -1;
        }
        PyObject *tmp2 = self->stream_callable;
        self->stream_callable = tmp;
        Py_XDECREF(tmp2);
    }

    tmp = self->raw_stream;
    Py_INCREF(value);
    self->raw_stream = value;
    Py_XDECREF(tmp);

    return 0;
}


static int
PTF_traverse(PTF_object *self, visitproc visit, void *arg)
{
    Py_VISIT(self->raw_stream);
    Py_VISIT(self->first_prefix);
    Py_VISIT(self->later_prefix);
    Py_VISIT(self->reset);
    Py_VISIT(self->bold);
    Py_VISIT(self->underline);
    return 0;
}

static int
PTF_clear(PTF_object *self)
{
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
    if(!(encoding = PyString_FromString("ascii")))
        return NULL;
    self = (PTF_object *)type->tp_alloc(type, 0);
    if(!self) {
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
    if(!(self->first_prefix = PyList_New(0))) {
        Py_DECREF(self);
        return NULL;
    }
    if(!(self->later_prefix = PyList_New(0))) {
        Py_DECREF(self);
        return NULL;
    }
    if(!(self->bold = PyString_FromString(""))) {
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
    static char *kwlist[] = {"stream", "width", "encoding", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|iz", kwlist,
        &stream, &self->width, &encoding))
        return -1;

    if (encoding) {
        tmp = self->encoding;
        self->encoding = encoding;
        Py_INCREF(encoding);
        Py_XDECREF(tmp);
    }

    return PTF_setstream(self, stream, NULL);
}

/* repeatedly reduce a callable invoking func(self), till it's no longer callable
  steals the passed in ref, and returns a new reference.
*/
static PyObject *
reduce_callable(PTF_object *self, PyObject *arg)
{
    PyObject *tmp;
    while(PyCallable_Check(arg)) {
        tmp = PyObject_CallFunctionObjArgs(arg, (PyObject *)self, NULL);
        if(!tmp)
            return tmp;
        Py_DECREF(arg);
        arg = tmp;
    }
    return arg;
}

static int
_write_prefix(PTF_object *self, int wrap) {
    PyObject *iter, *arg, *tmp;
    int ret;

    iter = self->in_first_line ? self->first_prefix : self->later_prefix;
    if(!(iter = PyObject_GetIter(iter)))
        return -1;

    while ((arg = PyIter_Next(iter))) {
        if(!(arg = reduce_callable(self, arg))) {
            Py_DECREF(iter);
            return -1;
        }

        if (arg == Py_None) {
            Py_DECREF(arg);
            continue;
        }

        if (PyUnicode_Check(arg)) {
            tmp = PyUnicode_AsEncodedString(arg, PyString_AS_STRING(self->encoding), "replace");
            Py_DECREF(arg);
            if (!tmp) {
                Py_DECREF(iter);
                return -1;
            }
            arg = tmp;
        }

        if (!(PyString_Check(arg))) {
            tmp = PyObject_Str(arg);
            Py_DECREF(arg);
            if (!tmp) {
                Py_DECREF(iter);
                return -1;
            }
            arg = tmp;
        }

        if (self->stream_callable) {
            tmp = PyObject_CallFunctionObjArgs(self->stream_callable, arg, NULL);
            Py_XDECREF(tmp);
            ret = tmp != NULL;
        } else {
            ret = PyFile_WriteObject(arg, self->raw_stream, Py_PRINT_RAW);
        }
        Py_DECREF(arg);
        if(ret) {
            Py_DECREF(iter);
            return -1;
        }

        if (wrap && (self->pos >= self->width))
            self->pos = self->width-10;
    }
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

    int i, maxlen, space;
    char *p;
    int i_wrap = self->wrap;
    int i_autoline = self->autoline;
    Py_ssize_t first_prune = 0, later_prune = 0;
    Py_ssize_t arg_len = 0;

#define getitem(ptr) ptr = PyDict_GetItemString(kwargs, #ptr);     \
        if (!ptr && PyErr_Occurred())                              \
            goto error;

    if(kwargs) {
        getitem(prefixes);
        getitem(prefix);
        getitem(first_prefixes);
        getitem(later_prefixes);
        getitem(later_prefix);
        getitem(wrap);
        getitem(autoline);
    }
#undef getitem

    if(autoline) {
        if(-1 == (i_autoline = PyObject_IsTrue(autoline))) {
            return NULL;
        }
    }

    if(wrap) {
        if(-1 == (i_wrap = PyObject_IsTrue(wrap))) {
            return NULL;
        }
    }

    if(prefixes) {
        if (first_prefixes || later_prefixes) {
            PyErr_SetString(PyExc_TypeError,
                "do not pass first_prefixes or later_prefixes "
                "if prefixes is passed");
            return NULL;
        }
        first_prefixes = later_prefixes = prefixes;
    }

    if(prefix) {
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
        if(PyList_Append(self->first_prefix, first_prefix))
            return NULL;
        first_prune = 1;
    } else if (first_prefixes) {
        first_prune = PyList_GET_SIZE(self->first_prefix);
        if(!(tmp = _PyList_Extend((PyListObject *)self->first_prefix, first_prefixes)))
            return NULL;
        Py_DECREF(tmp);
        first_prune -= PyList_GET_SIZE(self->first_prefix);
    }

    if (later_prefix) {
        if (later_prefixes) {
            PyErr_SetString(PyExc_TypeError,
                "do not pass both later_prefix and later_prefixes");
            goto finally;
        }
        if(PyList_Append(self->later_prefix, later_prefix))
            goto finally;
        later_prune = 1;
    } else if (later_prefixes) {
        later_prune = PyList_GET_SIZE(self->later_prefix);
        if(!(tmp = _PyList_Extend((PyListObject *)self->later_prefix, later_prefixes))) {
            later_prune = 0;
            goto finally;
        }
        Py_DECREF(tmp);
        later_prune -= PyList_GET_SIZE(self->later_prefix);
    }

    if(!(iterator = PyObject_GetIter(args)))
        goto finally;

    while ((arg = PyIter_Next(iterator))) {
        /* If we're at the start of the line, write our prefix.
         * There is a deficiency here: if neither our arg nor our
         * prefix affect _pos (both are escape sequences or empty)
         * we will write prefix more than once. This should not
         * matter.
         */

        if (self->pos == 0) {
            if (_write_prefix(self, i_wrap)) {
                goto finally;
            }
        }

        if(!(arg = reduce_callable(self, arg))) {
            goto finally;
        }

        if (arg == Py_None) {
            Py_CLEAR(arg);
            continue;
        }

        if (!PyString_Check(arg)) {
            tmp = PyObject_Str(arg);
            Py_CLEAR(arg);
            if(!tmp)
                goto finally;
            arg = tmp;
        }

        if (PyUnicode_Check(arg)) {
            tmp = PyUnicode_AsEncodedString(arg, self->encoding, "replace");
            Py_CLEAR(arg);
            if (!tmp)
                goto finally;
            arg = tmp;
        }
        
        /* unicode? */
        arg_len = PyString_GET_SIZE(arg);
        if(!arg_len) {
            /* There's nothing to write, so skip this bit... */
            Py_CLEAR(arg);
            continue;
        }

        while (i_wrap && ((self->pos + PyString_GET_SIZE(arg)) > self->width)) {
            PyObject *bit = NULL;
            arg_len = PyObject_Length(arg);
            /* We have to split. */
            maxlen = self->width - self->pos;
            p = PyString_AS_STRING(arg);
            for (space = -1, i = 0; *p++, i++;) {
                if (i == maxlen)
                    break;
                if (*p == ' ') {
                    space = i;
                    break;
                }
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
                    if(!(bit = PyString_FromString(""))) {
                        goto finally;
                    }
                } else {
                    /* Forcibly split this as far to the right as
                     * possible.
                     */
                    if(!(bit = PySequence_GetSlice(arg, 0, maxlen)))
                        goto finally;
                    tmp = PySequence_GetSlice(arg, maxlen, arg_len);
                    Py_CLEAR(arg);
                    if (!tmp) {
                        Py_DECREF(bit);
                        goto finally;
                    }
                    arg_len -= maxlen;
                    arg = tmp;
                }
            } else {
                /* Omit the space we split on.*/
                if(!(bit = PySequence_GetSlice(arg, 0, space)))
                    goto finally;
                tmp = PySequence_GetSlice(arg, space+1, arg_len);
                Py_CLEAR(arg);
                if (!tmp) {
                    Py_DECREF(bit);
                    goto finally;
                }
                arg_len -= space;
                arg = tmp;
            }

            int ret = 0;
            if (self->stream_callable) {
                tmp = PyObject_CallFunctionObjArgs(self->stream_callable, bit, NULL);
                Py_XDECREF(tmp);
                ret = tmp != NULL;
            } else {
                ret = PyFile_WriteObject(bit, self->raw_stream, Py_PRINT_RAW);
            }
            Py_DECREF(bit);
            if(ret)
                goto finally;

            self->pos = 0;
            self->in_first_line = 0;
            self->wrote_something = 0;
            if(_write_prefix(self, i_wrap)) {
                goto finally;
            }

        }

        if(self->stream_callable) {
            tmp = PyObject_CallFunctionObjArgs(self->stream_callable, arg, NULL);
            Py_XDECREF(tmp);
            if(!tmp)
                goto finally;
        } else {
            if(PyFile_WriteObject(arg, self->raw_stream, Py_PRINT_RAW))
                goto finally;
        }
        if(!i_autoline) {
            self->wrote_something = 1;
            self->pos += PyString_GET_SIZE(arg);
        }
        Py_CLEAR(arg);
    }

    if (i_autoline) {
        if (self->stream_callable) {
            tmp = PyObject_CallFunction(self->stream_callable, "(s)", "\n");
            if(!tmp)
                goto finally;
            Py_DECREF(tmp);
        } else {
            if (PyFile_WriteString("\n", self->raw_stream))
                goto finally;
        }
        self->in_first_line = 1;
        self->wrote_something = 0;
        self->pos = 0;
    }

finally:

    if(first_prune) {
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
        goto error;
    }

   Py_RETURN_NONE;

error:
    Py_XDECREF(iterator);
    Py_XDECREF(arg);
    return NULL;
}

static PyMethodDef PTF_methods[] = {
    {"write", (PyCFunction)PTF_write, METH_VARARGS | METH_KEYWORDS,
     "Return the name, combining the first and last name"
    },
    {"fg", (PyCFunction)PTF_returnemptystring, METH_VARARGS,
     ""
    },
    {"bg", (PyCFunction)PTF_returnemptystring, METH_VARARGS,
     ""
    },
    {"title", (PyCFunction)PTF_returnemptystring, METH_VARARGS,
     ""
    },
    {NULL}  /* Sentinel */
};


#define pyobj_struct(name) {#name,                         \
     (getter)PTF_getobj_##name, (setter)PTF_setobj_##name, \
     #name,                                                \
     NULL}


static PyGetSetDef PTF_getseters[] = {
    snakeoil_GETSET(PTF_object, "autoline", autoline),

    {"stream",
     (getter)PTF_getstream, (setter)PTF_setstream,
     "stream to write to",
     NULL},

    {"first_prefix",
     (getter)PTF_object_get_first_prefix, (setter)PTF_set_first_prefix,
     "the first prefix",
     NULL},

    {"later_prefix",
     (getter)PTF_object_get_later_prefix, (setter)PTF_set_later_prefix,
     "later prefixes",
     NULL},

    pyobj_struct(bold),
    pyobj_struct(underline),
    pyobj_struct(reset),

    {NULL} /* Sentinel */
};

#undef pyobj_struct

static PyMemberDef PTF_members[] = {
    {"width", T_INT, offsetof(PTF_object, width), 0,
         "width to split at"},
    {NULL}  /* Sentinel */
};



PyDoc_STRVAR(PTF_doc,
"PTF(iter1 [,iter2 [...]]) --> izip object\n\
\n\
Return a PTF object whose .next() method returns a tuple where\n\
the i-th element comes from the i-th iterable argument.  The .next()\n\
method continues until the shortest iterable in the argument sequence\n\
is exhausted and then it raises StopIteration.  Works like the zip()\n\
function but consumes less memory by returning an iterator instead of\n\
a list.");


static PyTypeObject PTF_type = {
        PyObject_HEAD_INIT(NULL)
        0,                              /* ob_size */
        "formatters.PlainTextFormatter",/* tp_name */
        sizeof(PTF_object),             /* tp_basicsize */
        0,                              /* tp_itemsize */
        (destructor)PTF_dealloc,        /* tp_dealloc */
        0,                              /* tp_print */
        0,                              /* tp_getattr */
        0,                              /* tp_setattr */
        0,                              /* tp_compare */
        0,                              /* tp_repr */
        0,                              /* tp_as_number */
        0,                              /* tp_as_sequence */
        0,                              /* tp_as_mapping */
        0,                              /* tp_hash */
        0,                              /* tp_call */
        0,                              /* tp_str */
        0,                              /* tp_getattro */
        0,                              /* tp_setattro */
        0,                              /* tp_as_buffer */
        Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_CLASS | Py_TPFLAGS_BASETYPE | Py_TPFLAGS_HAVE_GC,    /* tp_flags */
        PTF_doc,                        /* tp_doc */
        (traverseproc)PTF_traverse,                              /* tp_traverse */
        (inquiry)PTF_clear,                              /* tp_clear */
        0,                              /* tp_richcompare */
        0,                              /* tp_weaklistoffset */
        0,                              /* tp_iter */
        0,                              /* tp_iternext */
        PTF_methods,                    /* tp_methods */
        PTF_members,                    /* tp_members */
        PTF_getseters,                  /* tp_getset */
        0,                              /* tp_base */
        0,                              /* tp_dict */
        0,                              /* tp_descr_get */
        0,                              /* tp_descr_set */
        0,                              /* tp_dictoffset */
        (initproc)PTF_init,             /* tp_init */
        0,                              /* tp_alloc */
        PTF_new,                        /* tp_new */
};

PyDoc_STRVAR(formatters_module_doc, "my funky module\n");

PyMODINIT_FUNC
init_formatters()
{
    PyObject *m = Py_InitModule3("_formatters", NULL, formatters_module_doc);
    if (!m)
        return;

    PyObject *stream_closed = PyErr_NewException("snakeoil._formatters.StreamClosed", PyExc_KeyboardInterrupt, NULL);
    Py_INCREF(stream_closed);
    if (PyModule_AddObject(m, "StreamClosed", stream_closed))
        return;

    if (PyType_Ready(&PTF_type) < 0)
        return;
    Py_INCREF(&PTF_type);
    if (PyModule_AddObject(m, "PlainTextFormatter", (PyObject *)&PTF_type) == -1)
        return;
}
