/*
 * Copyright: 2006-2011 Brian Harring <ferringb@gmail.com>
 * License: BSD 3 clause
 *
 * common macros.
 */

#ifndef snakeoil_COMMON_HEADER
#define snakeoil_COMMON_HEADER 1

#include <Python.h>
#include "snakeoil/heapdef.h"

#define snakeoil_GET_ATTR(type, attr_name, func_post, attr)			\
static PyObject *													\
type##_get_##func_post (type *self, void *closure)					\
{																	\
	PyObject *v = attr;												\
	if(v) {															\
		Py_INCREF(attr);											\
		return v;													\
	}																\
	PyErr_SetString(PyExc_AttributeError, attr_name" isn't set");	\
	return NULL;													\
}

#define snakeoil_IMMUTABLE_ATTR_BOOL(type, name, attr, test)		\
static int															\
type##_set_##attr (type *self, PyObject *v, void *closure)			\
{																	\
	PyErr_SetString(PyExc_AttributeError, name" is immutable");		\
	return -1;														\
}																	\
snakeoil_ATTR_GET_BOOL(type, name, attr, test)

#define snakeoil_MUTABLE_ATTR_BOOL(type, name, attr, get_test,		\
	set_true, set_false)											\
snakeoil_ATTR_SET_BOOL(type, name, attr, set_true, set_false)		\
snakeoil_ATTR_GET_BOOL(type, name, attr, get_test)

#define snakeoil_ATTR_SET_BOOL(type, name, attr, set_true, set_false)	\
static int																\
type##_set_##attr (type *self, PyObject *v, void *closure)				\
{																		\
	int tmp;															\
	if(!v) {															\
		PyErr_SetString(PyExc_TypeError,								\
			"Cannot delete the "name" attribute");						\
		return -1;														\
	}																	\
	tmp = PyObject_IsTrue(v);											\
	if (tmp == -1)														\
		return -1;														\
	if(tmp) {															\
		set_true;														\
	} else {															\
		set_false;														\
	}																	\
	return 0;															\
}


#define snakeoil_ATTR_GET_BOOL(type, name, attr, test)				\
static PyObject *													\
type##_get_##attr (type *self, void *closure)						\
{																	\
	PyObject *s = (test) ? Py_True : Py_False;						\
	Py_INCREF(s);													\
	return s;														\
}

#define snakeoil_GETSET(type, doc, attr)	\
	{doc, (getter)type##_get_##attr ,		\
		(setter)type##_set_##attr , NULL}


#define snakeoil_FUNC_DESC(meth_name, class_name, func, methargs)	\
_snakeoil_FUNC_DESC(meth_name, class_name, func, methargs, 0)

#define _snakeoil_FUNC_DESC(meth_name, class_name, func, methargs, desc)	\
																			\
static PyTypeObject func##_type = {											\
	PyObject_HEAD_INIT(NULL)												\
	0,									/* ob_size */						\
	class_name,							/* tp_name */						\
	sizeof(PyObject),					/* tp_basicsize */					\
	0,									/* tp_itemsize */					\
	0,									/* tp_dealloc */					\
	0,									/* tp_print */						\
	0,									/* tp_getattr */					\
	0,									/* tp_setattr */					\
	0,									/* tp_compare */					\
	0,									/* tp_repr */						\
	0,									/* tp_as_number */					\
	0,									/* tp_as_sequence */				\
	0,									/* tp_as_mapping */					\
	0,									/* tp_hash */						\
	(ternaryfunc)func,					/* tp_call */						\
	0,									/* tp_str */						\
	0,									/* tp_getattro */					\
	0,									/* tp_setattro */					\
	0,									/* tp_as_buffer */					\
	Py_TPFLAGS_DEFAULT,					/* tp_flags */						\
	"cpython version of "#meth_name,	/* tp_doc */						\
	0,									/* tp_traverse */					\
	0,									/* tp_clear */						\
	0,									/* tp_richcompare */				\
	0,									/* tp_weaklistoffset */				\
	0,									/* tp_iter */						\
	0,									/* tp_iternext */					\
	0,									/* tp_methods */					\
	0,									/* tp_members */					\
	0,									/* tp_getset */						\
	0,									/* tp_base */						\
	0,									/* tp_dict */						\
	desc,								/* tp_descr_get */					\
	0,									/* tp_descr_set */					\
};

#define snakeoil_FUNC_BINDING(meth_name, class_name, func, methargs)	\
static PyObject *														\
func##_get_descr(PyObject *self, PyObject *obj, PyObject *type)			\
{																		\
	static PyMethodDef mdef = {meth_name, (PyCFunction)func, methargs,	\
		NULL};															\
	return PyCFunction_New(&mdef, obj);									\
}																		\
																		\
_snakeoil_FUNC_DESC(meth_name, class_name, func, methargs,				\
	func##_get_descr)


#define snakeoil_LOAD_MODULE2(module, namespace, failure_code)		\
Py_CLEAR((module));													\
if (! ((module) = PyImport_ImportModule(namespace))) {				\
	failure_code;													\
}

#define snakeoil_LOAD_MODULE(module, namespace)						\
snakeoil_LOAD_MODULE2((module), (namespace), return)

#define snakeoil_LOAD_ATTR2(target, module, attr, failure_code)		\
Py_XDECREF((target));												\
if (! ((target) = PyObject_GetAttrString((module), (attr))) ) {		\
	Py_XDECREF((module));											\
	failure_code;													\
}																	\

#define snakeoil_LOAD_ATTR(target, module, attr)					\
snakeoil_LOAD_ATTR2((target), (module), (attr), return)

#define snakeoil_LOAD_SINGLE_ATTR2(target, namespace, attr,			\
	failure_code)													\
{																	\
	PyObject *_m = NULL;											\
	snakeoil_LOAD_MODULE2(_m, (namespace), failure_code);			\
	snakeoil_LOAD_ATTR2((target), _m, (attr), failure_code);		\
	Py_DECREF(_m);													\
}

#define snakeoil_LOAD_SINGLE_ATTR(target, namespace, attr)			\
snakeoil_LOAD_SINGLE_ATTR2((target), (namespace), (attr), return)

#define snakeoil_LOAD_STRING2(target, char_p, failure_code)			\
if (!(target)) {													\
	if (! ((target) = PyString_FromString((char_p)))) {				\
		failure_code;												\
	}																\
}

#define snakeoil_LOAD_STRING(target, char_p)						\
snakeoil_LOAD_STRING2((target), (char_p), return)

#endif
