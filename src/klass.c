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
#include "structmember.h"
#include <ceval.h>

static PyObject *snakeoil_equality_attr = NULL;
static PyObject *snakeoil__orig_attr = NULL;
static PyObject *snakeoil__new_attr = NULL;


/* Note since the redirect target is a tuple of strings, we don't do
 * GC on the object- it can only refer to noncyclic targets.
 */

typedef struct {
	PyObject_HEAD
	PyObject *redirect_target;
} snakeoil_GetAttrProxy;

static void
snakeoil_GetAttrProxy_dealloc(snakeoil_GetAttrProxy *self)
{
	Py_CLEAR(self->redirect_target);
	self->ob_type->tp_free((PyObject *)self);
}

static PyObject *
snakeoil_GetAttrProxy_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	snakeoil_GetAttrProxy *self;
	PyObject *alias_attr;

	if (!PyArg_ParseTuple(args, "S:__new__", &alias_attr))
		return NULL;
	self = (snakeoil_GetAttrProxy *)type->tp_alloc(type, 0);

	if (self) {
		self->redirect_target = alias_attr;
		Py_INCREF(alias_attr);
	}
	return (PyObject *)self;
}

static PyObject *
snakeoil_GetAttrProxy_call(snakeoil_GetAttrProxy *self, PyObject *args,
	PyObject *kwds)
{
	PyObject *attr, *real_obj, *tmp = NULL;

	if (PyArg_ParseTuple(args, "OS:__call__", &real_obj, &attr)) {
		if (Py_EnterRecursiveCall(" in GetAttrProxy.__call__ "))
			return NULL;
		real_obj = PyObject_GenericGetAttr(real_obj, self->redirect_target);
		if (real_obj) {
			tmp = PyObject_GetAttr(real_obj, attr);
			Py_DECREF(real_obj);
		}
		Py_LeaveRecursiveCall();
	}
	return (PyObject *)tmp;
}

static PyObject *
snakeoil_GetAttrProxy_get(PyObject *func, PyObject *obj, PyObject *type)
{
	if (obj == Py_None)
		obj = NULL;
	return PyMethod_New(func, obj, type);
}

static PyTypeObject snakeoil_GetAttrProxyType = {
	PyObject_HEAD_INIT(NULL)
	0,											   /* ob_size */
	"snakeoil._klass.GetAttrProxy",				  /* tp_name */
	sizeof(snakeoil_GetAttrProxy),					/* tp_basicsize */
	0,											   /* tp_itemsize */
	(destructor)snakeoil_GetAttrProxy_dealloc,		/* tp_dealloc */
	0,											   /* tp_print */
	0,											   /* tp_getattr */
	0,											   /* tp_setattr */
	0,											   /* tp_compare */
	0,											   /* tp_repr */
	0,											   /* tp_as_number */
	0,											   /* tp_as_sequence */
	0,											   /* tp_as_mapping */
	0,											   /* tp_hash  */
	(ternaryfunc)snakeoil_GetAttrProxy_call,		  /* tp_call */
	(reprfunc)0,									 /* tp_str */
	0,											   /* tp_getattro */
	0,											   /* tp_setattro */
	0,											   /* tp_as_buffer */
	Py_TPFLAGS_DEFAULT,							  /* tp_flags */
	"GetAttrProxy object; used mainly for native __getattr__ speed",
													 /* tp_doc */
	0,											   /* tp_traverse */
	0,											   /* tp_clear */
	0,											   /* tp_richcompare */
	0,											   /* tp_weaklistoffset */
	0,											   /* tp_iter */
	0,											   /* tp_iternext */
	0,											   /* tp_methods */
	0,											   /* tp_members */
	0,											   /* tp_getset */
	0,											   /* tp_base */
	0,											   /* tp_dict */
	snakeoil_GetAttrProxy_get,					   /* tp_descr_get */
	0,											   /* tp_descr_set */
	0,											   /* tp_dictoffset */
	0,											   /* tp_init */
	0,											   /* tp_alloc */
	snakeoil_GetAttrProxy_new,						/* tp_new */

};

/*
 * Note since the hash_attr target is a string, we don't do
 * GC on the object- it can only refer to noncyclic targets.
 */

typedef struct {
	PyObject_HEAD
	PyObject *hash_attr;
} snakeoil_ReflectiveHash;

static void
snakeoil_ReflectiveHash_dealloc(snakeoil_ReflectiveHash *self)
{
	Py_CLEAR(self->hash_attr);
	self->ob_type->tp_free((PyObject *)self);
}

static PyObject *
snakeoil_ReflectiveHash_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	snakeoil_ReflectiveHash *self;
	PyObject *hash_attr;

	if (!PyArg_ParseTuple(args, "S:__new__", &hash_attr))
		return NULL;
	self = (snakeoil_ReflectiveHash *)type->tp_alloc(type, 0);

	if (self) {
		Py_INCREF(hash_attr);
		self->hash_attr = hash_attr;
	}
	return (PyObject *)self;
}

static PyObject *
snakeoil_ReflectiveHash_call(snakeoil_ReflectiveHash *self, PyObject *args,
	PyObject *kwds)
{
	PyObject *val = NULL;

	if (PyArg_ParseTuple(args, "O:__hash__", &val)) {
		val = PyObject_GetAttr(val, self->hash_attr);
	}
	return val;
}

static PyObject *
snakeoil_ReflectiveHash_get(PyObject *func, PyObject *obj, PyObject *type)
{
	if (obj == Py_None)
		obj = NULL;
	return PyMethod_New(func, obj, type);
}

static PyTypeObject snakeoil_ReflectiveHashType = {
	PyObject_HEAD_INIT(NULL)
	0,											   /* ob_size */
	"snakeoil._klass.ReflectiveHash",				  /* tp_name */
	sizeof(snakeoil_ReflectiveHash),					/* tp_basicsize */
	0,											   /* tp_itemsize */
	(destructor)snakeoil_ReflectiveHash_dealloc,		/* tp_dealloc */
	0,											   /* tp_print */
	0,											   /* tp_getattr */
	0,											   /* tp_setattr */
	0,											   /* tp_compare */
	0,											   /* tp_repr */
	0,											   /* tp_as_number */
	0,											   /* tp_as_sequence */
	0,											   /* tp_as_mapping */
	0,											   /* tp_hash  */
	(ternaryfunc)snakeoil_ReflectiveHash_call,		  /* tp_call */
	(reprfunc)0,									 /* tp_str */
	0,											   /* tp_getattro */
	0,											   /* tp_setattro */
	0,											   /* tp_as_buffer */
	Py_TPFLAGS_DEFAULT,							  /* tp_flags */
	"ReflectiveHash; used mainly for near native __hash__ speed"
		" when the hash value is precomputed on an object",
													 /* tp_doc */
	0,											   /* tp_traverse */
	0,											   /* tp_clear */
	0,											   /* tp_richcompare */
	0,											   /* tp_weaklistoffset */
	0,											   /* tp_iter */
	0,											   /* tp_iternext */
	0,											   /* tp_methods */
	0,											   /* tp_members */
	0,											   /* tp_getset */
	0,											   /* tp_base */
	0,											   /* tp_dict */
	snakeoil_ReflectiveHash_get,					   /* tp_descr_get */
	0,											   /* tp_descr_set */
	0,											   /* tp_dictoffset */
	0,											   /* tp_init */
	0,											   /* tp_alloc */
	snakeoil_ReflectiveHash_new,						/* tp_new */

};

typedef struct {
	PyObject_HEAD
	PyObject *storage_attr;
	PyObject *function;
	PyObject *singleton;
	PyObject *doc;
	int use_setattr;
	int use_singleton;
} snakeoil_InternalJitAttr;

static PyMemberDef snakeoil_InternalJitAttr_members[] = {
	{"storage_attr", T_OBJECT_EX, offsetof(snakeoil_InternalJitAttr, storage_attr),
		READONLY, "attribute the value is cached in"},
	{"function", T_OBJECT_EX, offsetof(snakeoil_InternalJitAttr, function),
		READONLY, "functor to cache values from"},
	{"singleton", T_OBJECT_EX, offsetof(snakeoil_InternalJitAttr, singleton),
		READONLY, "singleton value to look for if regeneration is needed, or if unset"},
	{"__doc__", T_OBJECT, offsetof(snakeoil_InternalJitAttr,doc), READONLY},
	{NULL}
};

static int
snakeoil_InternalJitAttr_clear(snakeoil_InternalJitAttr *self)
{
	Py_CLEAR(self->storage_attr);
	Py_CLEAR(self->function);
	Py_CLEAR(self->singleton);
	Py_CLEAR(self->doc);
	return 0;
}
static void
snakeoil_InternalJitAttr_dealloc(snakeoil_InternalJitAttr *self)
{
	self->ob_type->tp_clear((PyObject *)self);
	self->ob_type->tp_free((PyObject *)self);
}

static PyObject *
snakeoil_InternalJitAttr_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	snakeoil_InternalJitAttr *self;
	PyObject *attr = NULL, *func = NULL, *singleton = NULL,
		*use_setattr_obj = NULL, *use_singleton_obj = NULL,
		*doc = NULL;

	int use_setattr = 0;
	int use_singleton = 1;

	static char *kwlist[] = {"func", "attr_name", "singleton", "use_cls_setattr",
		"use_singleton", "doc", NULL};

	if (!PyArg_ParseTupleAndKeywords(args, kwds, "OS|OOOO:__new__",
		kwlist,
		&func, &attr, &singleton, &use_setattr_obj, &use_singleton_obj, &doc))
		return NULL;

	if (use_setattr_obj) {
		if (-1 == (use_setattr = PyObject_IsTrue(use_setattr_obj))) {
			return NULL;
		}
	}

	if (use_singleton_obj) {
		if (-1 == (use_singleton = PyObject_IsTrue(use_singleton_obj))) {
			return NULL;
		}
	}

	if (doc == NULL || doc == Py_None) {
		// Steal the doc from the func now.
		doc = PyObject_GetAttrString(func, "__doc__");
		PyErr_Clear();
	}

	self = (snakeoil_InternalJitAttr *)type->tp_alloc(type, 0);
	if (self) {
		Py_INCREF(attr);
		self->storage_attr = attr;
		Py_INCREF(func);
		self->function = func;
		if (!singleton) {
			singleton = Py_None;
		}
		Py_INCREF(singleton);
		self->singleton = singleton;
		self->use_setattr = use_setattr;
		self->use_singleton = use_singleton;
		Py_INCREF(doc);
		self->doc = doc;
	}
	return (PyObject *)self;
}

static int
snakeoil_InternalJitAttr_traverse(snakeoil_InternalJitAttr *self,
	visitproc visit, void *arg)
{
	Py_VISIT(self->function);
	Py_VISIT(self->singleton);
	return 0;
}

static PyObject *
snakeoil_InternalJitAttr_get(PyObject *self_pyo, PyObject *obj,
	PyObject *type)
{
	PyObject *result = NULL;
	snakeoil_InternalJitAttr *self = (snakeoil_InternalJitAttr *)self_pyo;
	// mimic property behaviour.
	if (!obj || obj == Py_None) {
		Py_INCREF(self_pyo);
		return self_pyo;
	}

	if (self->use_singleton) {
		if (Py_EnterRecursiveCall(" in InternalJitAttr.__get__ "))
			return NULL;

		result = PyObject_GetAttr(obj, self->storage_attr);

		Py_LeaveRecursiveCall();

		if (!result) {
			if (!PyErr_ExceptionMatches(PyExc_AttributeError)) {
				return result;
			}
			PyErr_Clear();
		} else if (self->singleton != result) {
			return result;
		} else {
			// got the singleton back...
			Py_DECREF(result);
		}
	}

	// generate the attr.
	result = PyObject_CallFunctionObjArgs(self->function, obj, NULL);
	if (result) {
		if (self->use_setattr) {
			if (-1 == PyObject_SetAttr(obj, self->storage_attr, result)) {
				Py_CLEAR(result);
			}
		} else {
			if (-1 == PyObject_GenericSetAttr(obj, self->storage_attr, result)) {
				Py_CLEAR(result);
			}
		}
	}
	return result;
}


static PyTypeObject snakeoil_InternalJitAttrType = {
	PyObject_HEAD_INIT(NULL)
	0,											   /* ob_size */
	"snakeoil._klass.InternalJitAttr",				  /* tp_name */
	sizeof(snakeoil_InternalJitAttr),					/* tp_basicsize */
	0,											   /* tp_itemsize */
	(destructor)snakeoil_InternalJitAttr_dealloc,		/* tp_dealloc */
	0,											   /* tp_print */
	0,											   /* tp_getattr */
	0,											   /* tp_setattr */
	0,											   /* tp_compare */
	0,											   /* tp_repr */
	0,											   /* tp_as_number */
	0,											   /* tp_as_sequence */
	0,											   /* tp_as_mapping */
	0,											   /* tp_hash  */
	0,											   /* tp_call */
	(reprfunc)0,									 /* tp_str */
	0,											   /* tp_getattro */
	0,											   /* tp_setattro */
	0,											   /* tp_as_buffer */
	Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,		 /* tp_flags */
	"InternalJitAttr object; basis of JIT cached attr access",
													 /* tp_doc */
	(traverseproc)snakeoil_InternalJitAttr_traverse, /* tp_traverse */
	(inquiry)snakeoil_InternalJitAttr_clear,		 /* tp_clear */
	0,											   /* tp_richcompare */
	0,											   /* tp_weaklistoffset */
	0,											   /* tp_iter */
	0,											   /* tp_iternext */
	0,											   /* tp_methods */
	snakeoil_InternalJitAttr_members,			   /* tp_members */
	0,											   /* tp_getset */
	0,											   /* tp_base */
	0,											   /* tp_dict */
	snakeoil_InternalJitAttr_get,					   /* tp_descr_get */
	0,											   /* tp_descr_set */
	0,											   /* tp_dictoffset */
	0,											   /* tp_init */
	0,											   /* tp_alloc */
	snakeoil_InternalJitAttr_new,						/* tp_new */

};

static inline PyObject *
internal_generic_equality(PyObject *inst1, PyObject *inst2,
	int desired)
{
	if (!inst1) {
		PyErr_SetString(PyExc_TypeError,
			"__eq__ or __ne__ method was invalidly assigned transferred across "
				"classes");
		return NULL;
	}
	if (inst1 == inst2) {
		PyObject *res = desired == Py_EQ ? Py_True : Py_False;
		Py_INCREF(res);
		return res;
	}

	PyObject *attrs = PyObject_GetAttr(inst1, snakeoil_equality_attr);
	if (!attrs)
		return NULL;
	if (!PyTuple_CheckExact(attrs)) {
		PyErr_SetString(PyExc_TypeError,
			"__attr_comparison__ must be a tuple");
		return NULL;
	}

	Py_ssize_t idx = 0;
	PyObject *attr1, *attr2;
	// if Py_EQ, break on not equal, else on equal
	for (; idx < PyTuple_GET_SIZE(attrs); idx++) {

		attr1 = PyObject_GetAttr(inst1, PyTuple_GET_ITEM(attrs, idx));
		if (!attr1) {
			if (!PyErr_ExceptionMatches(PyExc_AttributeError))
				return NULL;
			 PyErr_Clear();
		}

		attr2 = PyObject_GetAttr(inst2, PyTuple_GET_ITEM(attrs, idx));
		if (!attr2) {
			if (!PyErr_ExceptionMatches(PyExc_AttributeError)) {
				Py_XDECREF(attr1);
				return NULL;
			}
			PyErr_Clear();
		}
		if (!attr1) {
			if (attr2) {
				Py_DECREF(attr2);
				Py_DECREF(attrs);
				if (desired == Py_EQ) {
					Py_RETURN_FALSE;
				}
				Py_RETURN_TRUE;
			}
			continue;
		} else if (!attr2) {
			Py_DECREF(attr1);
			Py_DECREF(attrs);
			if (desired == Py_EQ) {
				Py_RETURN_FALSE;
			}
			Py_RETURN_TRUE;
		}
		int ret = PyObject_RichCompareBool(attr1, attr2, desired);
		Py_DECREF(attr1);
		Py_DECREF(attr2);
		if (0 > ret) {
			Py_DECREF(attrs);
			return NULL;
		} else if (0 == ret) {
			if (desired == Py_EQ) {
				Py_DECREF(attrs);
				Py_RETURN_FALSE;
			}
		} else if (desired == Py_NE) {
			Py_DECREF(attrs);
			Py_RETURN_TRUE;
		}
	}
	Py_DECREF(attrs);
	if (desired == Py_EQ) {
		Py_RETURN_TRUE;
	}
	Py_RETURN_FALSE;
}

static PyObject *
snakeoil_generic_equality_eq(PyObject *self, PyObject *other)
{
	return internal_generic_equality(self, other, Py_EQ);
}

static PyObject *
snakeoil_generic_equality_ne(PyObject *self, PyObject *other)
{
	return internal_generic_equality(self, other, Py_NE);
}

snakeoil_FUNC_BINDING("generic_eq", "snakeoil._klass.generic_eq",
	snakeoil_generic_equality_eq, METH_O|METH_COEXIST)

snakeoil_FUNC_BINDING("generic_ne", "snakeoil._klass.generic_ne",
	snakeoil_generic_equality_ne, METH_O)

static PyObject *
snakeoil_mapping_get(PyObject *self, PyObject *args)
{
	PyObject *key, *default_val = Py_None;
	if (!self) {
		PyErr_SetString(PyExc_TypeError,
			"need to be called with a mapping as the first arg");
		return NULL;
	}
	if (!PyArg_UnpackTuple(args, "get", 1, 2, &key, &default_val))
		return NULL;

	PyObject *ret = PyObject_GetItem(self, key);
	if (ret) {
		return ret;
	} else if (!PyErr_ExceptionMatches(PyExc_KeyError)) {
		return NULL;
	}

	PyErr_Clear();
	Py_INCREF(default_val);
	return default_val;
}

static PyMethodDef snakeoil_mapping_get_def = {
	"get", snakeoil_mapping_get, METH_VARARGS, NULL};

static PyObject *
snakeoil_mapping_get_descr(PyObject *self, PyObject *obj, PyObject *type)
{
	return PyCFunction_New(&snakeoil_mapping_get_def, obj);
}

static PyTypeObject snakeoil_GetType = {
	PyObject_HEAD_INIT(NULL)
	0,											   /* ob_size */
	"snakeoil_get_type",							  /* tp_name */
	sizeof(PyObject),								/* tp_basicsize */
	0,											   /* tp_itemsize */
	0,											   /* tp_dealloc */
	0,											   /* tp_print */
	0,											   /* tp_getattr */
	0,											   /* tp_setattr */
	0,											   /* tp_compare */
	0,											   /* tp_repr */
	0,											   /* tp_as_number */
	0,											   /* tp_as_sequence */
	0,											   /* tp_as_mapping */
	0,											   /* tp_hash  */
	0,											   /* tp_call */
	0,											   /* tp_str */
	0,											   /* tp_getattro */
	0,											   /* tp_setattro */
	0,											   /* tp_as_buffer */
	Py_TPFLAGS_DEFAULT,							  /* tp_flags */
	"type of the get proxy",						 /* tp_doc */
	0,											   /* tp_traverse */
	0,											   /* tp_clear */
	0,											   /* tp_richcompare */
	0,											   /* tp_weaklistoffset */
	0,											   /* tp_iter */
	0,											   /* tp_iternext */
	0,											   /* tp_methods */
	0,											   /* tp_members */
	0,											   /* tp_getset */
	0,											   /* tp_base */
	0,											   /* tp_dict */
	snakeoil_mapping_get_descr,					   /* tp_descr_get */
	0,											   /* tp_descr_set */
};

static PyObject *
snakeoil_mapping_contains(PyObject *self, PyObject *key)
{
	if (!self) {
		PyErr_SetString(PyExc_TypeError,
			"need to be called with a mapping as the first arg");
		return NULL;
	}

	PyObject *ret = PyObject_GetItem(self, key);
	if (ret) {
		Py_DECREF(ret);
		ret = Py_True;
	} else if (!PyErr_ExceptionMatches(PyExc_KeyError)) {
		return NULL;
	} else {
		PyErr_Clear();
		ret = Py_False;
	}
	Py_INCREF(ret);
	return ret;
}

static PyMethodDef snakeoil_mapping_contains_def = {
	"contains", snakeoil_mapping_contains, METH_O|METH_COEXIST, NULL};

static PyObject *
snakeoil_mapping_contains_descr(PyObject *self, PyObject *obj, PyObject *type)
{
	return PyCFunction_New(&snakeoil_mapping_contains_def, obj);
}

static PyTypeObject snakeoil_ContainsType = {
	PyObject_HEAD_INIT(NULL)
	0,											   /* ob_size */
	"snakeoil_contains_type",						 /* tp_name */
	sizeof(PyObject),								/* tp_basicsize */
	0,											   /* tp_itemsize */
	0,											   /* tp_dealloc */
	0,											   /* tp_print */
	0,											   /* tp_getattr */
	0,											   /* tp_setattr */
	0,											   /* tp_compare */
	0,											   /* tp_repr */
	0,											   /* tp_as_number */
	0,											   /* tp_as_sequence */
	0,											   /* tp_as_mapping */
	0,											   /* tp_hash  */
	0,											   /* tp_call */
	0,											   /* tp_str */
	0,											   /* tp_getattro */
	0,											   /* tp_setattro */
	0,											   /* tp_as_buffer */
	Py_TPFLAGS_DEFAULT,							  /* tp_flags */
	"type of the contains proxy",					/* tp_doc */
	0,											   /* tp_traverse */
	0,											   /* tp_clear */
	0,											   /* tp_richcompare */
	0,											   /* tp_weaklistoffset */
	0,											   /* tp_iter */
	0,											   /* tp_iternext */
	0,											   /* tp_methods */
	0,											   /* tp_members */
	0,											   /* tp_getset */
	0,											   /* tp_base */
	0,											   /* tp_dict */
	snakeoil_mapping_contains_descr,				  /* tp_descr_get */
	0,											   /* tp_descr_set */
};


static PyObject *
snakeoil_mapping_slot_getitem(PyObject *self, PyObject *key)
{
	PyObject *value = PyObject_GetAttr(self, key);
	if (value)
		return value;
	if (PyErr_ExceptionMatches(PyExc_TypeError)) {
		return NULL;
	} else if (!PyErr_ExceptionMatches(PyExc_AttributeError) &&
		(PyString_Check(key) || PyUnicode_Check(key))) {
		// only one potential we care about... TypeError if key wasn't a string.
		// some form of bug in the __getattr__...
		return value;
	}
	Py_INCREF(key);
	PyErr_SetObject(PyExc_KeyError, key);
	return value;
}

static PyMethodDef snakeoil_mapping_slot_getitem_def = {
	"getitem", snakeoil_mapping_slot_getitem, METH_O|METH_COEXIST, NULL};

static PyObject *
snakeoil_mapping_slot_getitem_descr(PyObject *self, PyObject *obj, PyObject *type)
{
	return PyCFunction_New(&snakeoil_mapping_slot_getitem_def, obj);
}

static PyTypeObject snakeoil_AttrGetItemType = {
	PyObject_HEAD_INIT(NULL)
	0,											   /* ob_size */
	"snakeoil_attr_getitem_type",					/* tp_name */
	sizeof(PyObject),								/* tp_basicsize */
	0,											   /* tp_itemsize */
	0,											   /* tp_dealloc */
	0,											   /* tp_print */
	0,											   /* tp_getattr */
	0,											   /* tp_setattr */
	0,											   /* tp_compare */
	0,											   /* tp_repr */
	0,											   /* tp_as_number */
	0,											   /* tp_as_sequence */
	0,											   /* tp_as_mapping */
	0,											   /* tp_hash  */
	0,											   /* tp_call */
	0,											   /* tp_str */
	0,											   /* tp_getattro */
	0,											   /* tp_setattro */
	0,											   /* tp_as_buffer */
	Py_TPFLAGS_DEFAULT,							  /* tp_flags */
	"type of the getitem proxy",					 /* tp_doc */
	0,											   /* tp_traverse */
	0,											   /* tp_clear */
	0,											   /* tp_richcompare */
	0,											   /* tp_weaklistoffset */
	0,											   /* tp_iter */
	0,											   /* tp_iternext */
	0,											   /* tp_methods */
	0,											   /* tp_members */
	0,											   /* tp_getset */
	0,											   /* tp_base */
	0,											   /* tp_dict */
	snakeoil_mapping_slot_getitem_descr,			 /* tp_descr_get */
	0,											   /* tp_descr_set */
};

static PyObject *
snakeoil_mapping_slot_setitem(PyObject *self, PyObject *args)
{
	PyObject *key, *value;
	if (!PyArg_UnpackTuple(args, "snakeoil_attr_setitem", 2, 2, &key, &value)) {
		// should be impossible, but better safe then sorry.
		return NULL;
	}
	int result = PyObject_SetAttr(self, key, value);
	if (-1 == result) {
		return (PyObject *)NULL;
	}
	Py_RETURN_NONE;
}

static PyMethodDef snakeoil_mapping_slot_setitem_def = {
	"setitem", snakeoil_mapping_slot_setitem, METH_VARARGS|METH_COEXIST, NULL};

static PyObject *
snakeoil_mapping_slot_setitem_descr(PyObject *self, PyObject *obj, PyObject *type)
{
	return PyCFunction_New(&snakeoil_mapping_slot_setitem_def, obj);
}

static PyTypeObject snakeoil_AttrSetItemType = {
	PyObject_HEAD_INIT(NULL)
	0,											   /* ob_size */
	"snakeoil_attr_setitem_type",					/* tp_name */
	sizeof(PyObject),								/* tp_basicsize */
	0,											   /* tp_itemsize */
	0,											   /* tp_dealloc */
	0,											   /* tp_print */
	0,											   /* tp_getattr */
	0,											   /* tp_setattr */
	0,											   /* tp_compare */
	0,											   /* tp_repr */
	0,											   /* tp_as_number */
	0,											   /* tp_as_sequence */
	0,											   /* tp_as_mapping */
	0,											   /* tp_hash  */
	0,											   /* tp_call */
	0,											   /* tp_str */
	0,											   /* tp_getattro */
	0,											   /* tp_setattro */
	0,											   /* tp_as_buffer */
	Py_TPFLAGS_DEFAULT,							  /* tp_flags */
	"type of the setitem proxy",					 /* tp_doc */
	0,											   /* tp_traverse */
	0,											   /* tp_clear */
	0,											   /* tp_richcompare */
	0,											   /* tp_weaklistoffset */
	0,											   /* tp_iter */
	0,											   /* tp_iternext */
	0,											   /* tp_methods */
	0,											   /* tp_members */
	0,											   /* tp_getset */
	0,											   /* tp_base */
	0,											   /* tp_dict */
	snakeoil_mapping_slot_setitem_descr,			 /* tp_descr_get */
	0,											   /* tp_descr_set */
};

static PyObject *
snakeoil_mapping_slot_delitem_slow(PyObject *self, PyObject *key)
{

	// because pythons __slots__ is retarded (see python issue 7604),
	// do a hasattr first.
	if (PyObject_HasAttr(self, key)) {
		if (0 == PyObject_DelAttr(self, key)) {
			Py_RETURN_NONE;
		}
		// convert AttributeError into KeyError... let the rest
		// pass thru
		if (PyErr_ExceptionMatches(PyExc_AttributeError)) {
			PyErr_SetObject(PyExc_KeyError, key);
		}
	} else {
		PyErr_SetObject(PyExc_KeyError, key);
	}
	return NULL;
}

static PyMethodDef snakeoil_mapping_slot_delitem_slow_def = {
	"delitem", snakeoil_mapping_slot_delitem_slow, METH_O|METH_COEXIST, NULL};

static PyObject *
snakeoil_mapping_slot_delitem_slow_descr(PyObject *self, PyObject *obj, PyObject *type)
{
	return PyCFunction_New(&snakeoil_mapping_slot_delitem_slow_def, obj);
}

static PyTypeObject snakeoil_AttrDelItemSlowType = {
	PyObject_HEAD_INIT(NULL)
	0,											   /* ob_size */
	"snakeoil_attr_delitem_slow_type",				/* tp_name */
	sizeof(PyObject),								/* tp_basicsize */
	0,											   /* tp_itemsize */
	0,											   /* tp_dealloc */
	0,											   /* tp_print */
	0,											   /* tp_getattr */
	0,											   /* tp_setattr */
	0,											   /* tp_compare */
	0,											   /* tp_repr */
	0,											   /* tp_as_number */
	0,											   /* tp_as_sequence */
	0,											   /* tp_as_mapping */
	0,											   /* tp_hash  */
	0,											   /* tp_call */
	0,											   /* tp_str */
	0,											   /* tp_getattro */
	0,											   /* tp_setattro */
	0,											   /* tp_as_buffer */
	Py_TPFLAGS_DEFAULT,							  /* tp_flags */
	"type of the delitem proxy",					 /* tp_doc */
	0,											   /* tp_traverse */
	0,											   /* tp_clear */
	0,											   /* tp_richcompare */
	0,											   /* tp_weaklistoffset */
	0,											   /* tp_iter */
	0,											   /* tp_iternext */
	0,											   /* tp_methods */
	0,											   /* tp_members */
	0,											   /* tp_getset */
	0,											   /* tp_base */
	0,											   /* tp_dict */
	snakeoil_mapping_slot_delitem_slow_descr,	   /* tp_descr_get */
	0,											   /* tp_descr_set */
};

static PyObject *
snakeoil_mapping_slot_delitem_fast(PyObject *self, PyObject *key)
{
	// for use in python versions that don't have to do the double lookup.
	// because pythons __slots__ is retarded (see python issue 7604),
	// do a hasattr first.
	if (0 == PyObject_DelAttr(self, key)) {
		Py_RETURN_NONE;
	}
	// convert AttributeError into KeyError... let the rest
	// pass thru
	if (PyErr_ExceptionMatches(PyExc_AttributeError)) {
		PyErr_SetObject(PyExc_KeyError, key);
	}
	return NULL;
}

static PyMethodDef snakeoil_mapping_slot_delitem_fast_def = {
	"delitem", snakeoil_mapping_slot_delitem_fast, METH_O|METH_COEXIST, NULL};

static PyObject *
snakeoil_mapping_slot_delitem_fast_descr(PyObject *self, PyObject *obj, PyObject *type)
{
	return PyCFunction_New(&snakeoil_mapping_slot_delitem_fast_def, obj);
}

static PyTypeObject snakeoil_AttrDelItemFastType = {
	PyObject_HEAD_INIT(NULL)
	0,											   /* ob_size */
	"snakeoil_attr_delitem_fast_type",				/* tp_name */
	sizeof(PyObject),								/* tp_basicsize */
	0,											   /* tp_itemsize */
	0,											   /* tp_dealloc */
	0,											   /* tp_print */
	0,											   /* tp_getattr */
	0,											   /* tp_setattr */
	0,											   /* tp_compare */
	0,											   /* tp_repr */
	0,											   /* tp_as_number */
	0,											   /* tp_as_sequence */
	0,											   /* tp_as_mapping */
	0,											   /* tp_hash  */
	0,											   /* tp_call */
	0,											   /* tp_str */
	0,											   /* tp_getattro */
	0,											   /* tp_setattro */
	0,											   /* tp_as_buffer */
	Py_TPFLAGS_DEFAULT,							  /* tp_flags */
	"type of the delitem proxy",					 /* tp_doc */
	0,											   /* tp_traverse */
	0,											   /* tp_clear */
	0,											   /* tp_richcompare */
	0,											   /* tp_weaklistoffset */
	0,											   /* tp_iter */
	0,											   /* tp_iternext */
	0,											   /* tp_methods */
	0,											   /* tp_members */
	0,											   /* tp_getset */
	0,											   /* tp_base */
	0,											   /* tp_dict */
	snakeoil_mapping_slot_delitem_fast_descr,	   /* tp_descr_get */
	0,											   /* tp_descr_set */
};

static PyObject *
snakeoil_mapping_slot_contains(PyObject *self, PyObject *key)
{
	if (PyObject_HasAttr(self, key)) {
		Py_RETURN_TRUE;
	}
	Py_RETURN_FALSE;
}

static PyMethodDef snakeoil_mapping_slot_contains_def = {
	"contains", snakeoil_mapping_slot_contains, METH_O|METH_COEXIST, NULL};

static PyObject *
snakeoil_mapping_slot_contains_descr(PyObject *self, PyObject *obj, PyObject *type)
{
	return PyCFunction_New(&snakeoil_mapping_slot_contains_def, obj);
}

static PyTypeObject snakeoil_AttrContainsType = {
	PyObject_HEAD_INIT(NULL)
	0,											   /* ob_size */
	"snakeoil_attr_contains_type",				   /* tp_name */
	sizeof(PyObject),								/* tp_basicsize */
	0,											   /* tp_itemsize */
	0,											   /* tp_dealloc */
	0,											   /* tp_print */
	0,											   /* tp_getattr */
	0,											   /* tp_setattr */
	0,											   /* tp_compare */
	0,											   /* tp_repr */
	0,											   /* tp_as_number */
	0,											   /* tp_as_sequence */
	0,											   /* tp_as_mapping */
	0,											   /* tp_hash  */
	0,											   /* tp_call */
	0,											   /* tp_str */
	0,											   /* tp_getattro */
	0,											   /* tp_setattro */
	0,											   /* tp_as_buffer */
	Py_TPFLAGS_DEFAULT,							  /* tp_flags */
	"type of the contains proxy",					/* tp_doc */
	0,											   /* tp_traverse */
	0,											   /* tp_clear */
	0,											   /* tp_richcompare */
	0,											   /* tp_weaklistoffset */
	0,											   /* tp_iter */
	0,											   /* tp_iternext */
	0,											   /* tp_methods */
	0,											   /* tp_members */
	0,											   /* tp_getset */
	0,											   /* tp_base */
	0,											   /* tp_dict */
	snakeoil_mapping_slot_contains_descr,			/* tp_descr_get */
	0,											   /* tp_descr_set */
};

static PyObject *
snakeoil_mapping_slot_pop(PyObject *self, PyObject *args)
{
	PyObject *key = NULL, *default_val = NULL;
	if (!PyArg_UnpackTuple(args, "snakeoil_attr_pop", 1, 2, &key, &default_val)) {
		// should be impossible, but better safe then sorry.
		return NULL;
	}
	PyObject *result = PyObject_GetAttr(self, key);
	if (result) {
		if (0 != PyObject_DelAttr(self, key)) {
			Py_DECREF(result);
			return NULL;
		}
	} else{
		if (!PyErr_ExceptionMatches(PyExc_AttributeError)) {
			return NULL;
		}
		if (default_val) {
			Py_INCREF(default_val);
			PyErr_Clear();
			return default_val;
		}
		PyErr_SetObject(PyExc_KeyError, key);
	}
	return result;
}

static PyMethodDef snakeoil_mapping_slot_pop_def = {
	"pop", snakeoil_mapping_slot_pop, METH_VARARGS|METH_COEXIST, NULL};

static PyObject *
snakeoil_mapping_slot_pop_descr(PyObject *self, PyObject *obj, PyObject *type)
{
	return PyCFunction_New(&snakeoil_mapping_slot_pop_def, obj);
}

static PyTypeObject snakeoil_AttrPopType = {
	PyObject_HEAD_INIT(NULL)
	0,											   /* ob_size */
	"snakeoil_attr_pop_type",						/* tp_name */
	sizeof(PyObject),								/* tp_basicsize */
	0,											   /* tp_itemsize */
	0,											   /* tp_dealloc */
	0,											   /* tp_print */
	0,											   /* tp_getattr */
	0,											   /* tp_setattr */
	0,											   /* tp_compare */
	0,											   /* tp_repr */
	0,											   /* tp_as_number */
	0,											   /* tp_as_sequence */
	0,											   /* tp_as_mapping */
	0,											   /* tp_hash  */
	0,											   /* tp_call */
	0,											   /* tp_str */
	0,											   /* tp_getattro */
	0,											   /* tp_setattro */
	0,											   /* tp_as_buffer */
	Py_TPFLAGS_DEFAULT,							  /* tp_flags */
	"type of the pop proxy",						 /* tp_doc */
	0,											   /* tp_traverse */
	0,											   /* tp_clear */
	0,											   /* tp_richcompare */
	0,											   /* tp_weaklistoffset */
	0,											   /* tp_iter */
	0,											   /* tp_iternext */
	0,											   /* tp_methods */
	0,											   /* tp_members */
	0,											   /* tp_getset */
	0,											   /* tp_base */
	0,											   /* tp_dict */
	snakeoil_mapping_slot_pop_descr,				  /* tp_descr_get */
	0,											   /* tp_descr_set */
};

static PyObject *
snakeoil_mapping_slot_get(PyObject *self, PyObject *args)
{
	PyObject *key = NULL, *default_val = NULL;
	if (!PyArg_UnpackTuple(args, "snakeoil_attr_get", 1, 2, &key, &default_val)) {
		// should be impossible, but better safe then sorry.
		return NULL;
	}
	PyObject *result = PyObject_GetAttr(self, key);
	if (!result) {
		if (!PyErr_ExceptionMatches(PyExc_AttributeError)) {
			return NULL;
		}
		PyErr_Clear();
		if (!default_val) {
			result = Py_None;
		} else {
			result = default_val;
		}
		Py_INCREF(result);;
	}
	return result;
}

static PyMethodDef snakeoil_mapping_slot_get_def = {
	"get", snakeoil_mapping_slot_get, METH_VARARGS|METH_COEXIST, NULL};

static PyObject *
snakeoil_mapping_slot_get_descr(PyObject *self, PyObject *obj, PyObject *type)
{
	return PyCFunction_New(&snakeoil_mapping_slot_get_def, obj);
}

static PyTypeObject snakeoil_AttrGetType = {
	PyObject_HEAD_INIT(NULL)
	0,											   /* ob_size */
	"snakeoil_attr_get_type",						/* tp_name */
	sizeof(PyObject),								/* tp_basicsize */
	0,											   /* tp_itemsize */
	0,											   /* tp_dealloc */
	0,											   /* tp_print */
	0,											   /* tp_getattr */
	0,											   /* tp_setattr */
	0,											   /* tp_compare */
	0,											   /* tp_repr */
	0,											   /* tp_as_number */
	0,											   /* tp_as_sequence */
	0,											   /* tp_as_mapping */
	0,											   /* tp_hash  */
	0,											   /* tp_call */
	0,											   /* tp_str */
	0,											   /* tp_getattro */
	0,											   /* tp_setattro */
	0,											   /* tp_as_buffer */
	Py_TPFLAGS_DEFAULT,							  /* tp_flags */
	"type of the get proxy",						 /* tp_doc */
	0,											   /* tp_traverse */
	0,											   /* tp_clear */
	0,											   /* tp_richcompare */
	0,											   /* tp_weaklistoffset */
	0,											   /* tp_iter */
	0,											   /* tp_iternext */
	0,											   /* tp_methods */
	0,											   /* tp_members */
	0,											   /* tp_getset */
	0,											   /* tp_base */
	0,											   /* tp_dict */
	snakeoil_mapping_slot_get_descr,				  /* tp_descr_get */
	0,											   /* tp_descr_set */
};

static PyObject *
snakeoil_mapping_slot_update(PyObject *self, PyObject *sequence)
{
	PyObject *iterator = PyObject_GetIter(sequence);
	PyObject *item = NULL;
	Py_ssize_t position = 0;
	int result = 0;

	if (!iterator)
		return NULL;

	while (item = PyIter_Next(iterator)) {
		if (PyTuple_CheckExact(item)) {
			// fast path this to avoid unpacking and other nasty checks
			if (2 == PyTuple_GET_SIZE(item)) {
				result = PyObject_SetAttr(self,
					PyTuple_GET_ITEM(item, 0), PyTuple_GET_ITEM(item, 1));
			} else {
				result = -2;
			}
		} else if (!PySequence_Check(item)) {
			result = -3;
		} else {
			// manually unpack the bugger.
			Py_ssize_t size = PySequence_Size(item);
			if (2 != size) {
				result = -2;
			} else if (-1 != size) {
				result = -1;
				PyObject *key = PySequence_GetItem(item, 0);
				if (key) {
					PyObject *value = PySequence_GetItem(item, 1);
					if (value) {
						result = PyObject_SetAttr(self, key, value);
						Py_DECREF(value);
					}
					Py_DECREF(key);
				}
			}
		}
		Py_DECREF(item);
		if (0 != result) {
			PyObject *errstr = NULL;
			if (-2 == result) {
				// wrong size.
				errstr = PyString_FromFormat(
					"attr dictionary update sequence element #%i has the wrong length",
					(int)position);
				if (errstr) {
					PyErr_SetObject(PyExc_ValueError, errstr);
				}
			} else if (-3 == result) {
				errstr = PyString_FromFormat(
					"cannot convert attr dictionary update sequence element #%i to a sequence",
					(int)position);
				if (errstr) {
					PyErr_SetObject(PyExc_TypeError, errstr);
				}
			} else if (-1 != result) {
				errstr = PyString_FromFormat(
					"unhandled result(%i) during update at position %i- constants changed?",
						(int)result, (int)position);
				if (errstr) {
					PyErr_SetObject(PyExc_RuntimeError, errstr);
				}
			}
			Py_XDECREF(errstr);
			break;
		}
		position++;
	}
	Py_DECREF(iterator);
	if (0 == result) {
		Py_RETURN_NONE;
	}
	return NULL;
}

static PyMethodDef snakeoil_mapping_slot_update_def = {
	"update", snakeoil_mapping_slot_update, METH_O|METH_COEXIST, NULL};

static PyObject *
snakeoil_mapping_slot_update_descr(PyObject *self, PyObject *obj, PyObject *type)
{
	return PyCFunction_New(&snakeoil_mapping_slot_update_def, obj);
}

static PyTypeObject snakeoil_AttrUpdateType = {
	PyObject_HEAD_INIT(NULL)
	0,											   /* ob_size */
	"snakeoil_attr_update_type",					 /* tp_name */
	sizeof(PyObject),								/* tp_basicsize */
	0,											   /* tp_itemsize */
	0,											   /* tp_dealloc */
	0,											   /* tp_print */
	0,											   /* tp_getattr */
	0,											   /* tp_setattr */
	0,											   /* tp_compare */
	0,											   /* tp_repr */
	0,											   /* tp_as_number */
	0,											   /* tp_as_sequence */
	0,											   /* tp_as_mapping */
	0,											   /* tp_hash  */
	0,											   /* tp_call */
	0,											   /* tp_str */
	0,											   /* tp_getattro */
	0,											   /* tp_setattro */
	0,											   /* tp_as_buffer */
	Py_TPFLAGS_DEFAULT,							  /* tp_flags */
	"type of the update proxy",					  /* tp_doc */
	0,											   /* tp_traverse */
	0,											   /* tp_clear */
	0,											   /* tp_richcompare */
	0,											   /* tp_weaklistoffset */
	0,											   /* tp_iter */
	0,											   /* tp_iternext */
	0,											   /* tp_methods */
	0,											   /* tp_members */
	0,											   /* tp_getset */
	0,											   /* tp_base */
	0,											   /* tp_dict */
	snakeoil_mapping_slot_update_descr,			  /* tp_descr_get */
	0,											   /* tp_descr_set */
};


PyObject *
snakeoil_protectedset_contains(PyObject *self, PyObject *key)
{
	PyObject *set = NULL;
	int result = -1;
	if (!(set = PyObject_GetAttr(self, snakeoil__orig_attr))) {
		return NULL;
	}
#if PY_MAJOR_VERSION > 2 || (PY_MAJOR_VERSION == 2 && PY_MINOR_VERSION >= 5)
	if (PyAnySet_Check(set)) {
		result = PySet_Contains(set, key);
	} else
#endif
	{

		result = PySequence_Contains(set, key);
	}
	Py_DECREF(set);
	if (result == 0) {
		if (!(set = PyObject_GetAttr(self, snakeoil__new_attr))) {
			return NULL;
		}

#if PY_MAJOR_VERSION > 2 || (PY_MAJOR_VERSION == 2 && PY_MINOR_VERSION >= 5)
		if (PyAnySet_Check(set)) {
			result = PySet_Contains(set, key);
		} else
#endif
		{
			result = PySequence_Contains(set, key);
		}
		Py_DECREF(set);
	}
	if (-1 == result) {
		return NULL;
	} else if (0 == result) {
		Py_RETURN_FALSE;
	}
	Py_RETURN_TRUE;
}

static PyMethodDef snakeoil_protectedset_contains_def = {
	"contains", snakeoil_protectedset_contains, METH_O|METH_COEXIST, NULL};

static PyObject *
snakeoil_protectedset_contains_descr(PyObject *self, PyObject *obj, PyObject *type)
{
	return PyCFunction_New(&snakeoil_protectedset_contains_def, obj);
}

static PyTypeObject snakeoil_ProtectedSetContainsType = {
	PyObject_HEAD_INIT(NULL)
	0,											   /* ob_size */
	"snakeoil_ProtectedSet_contains_type",		   /* tp_name */
	sizeof(PyObject),								/* tp_basicsize */
	0,											   /* tp_itemsize */
	0,											   /* tp_dealloc */
	0,											   /* tp_print */
	0,											   /* tp_getattr */
	0,											   /* tp_setattr */
	0,											   /* tp_compare */
	0,											   /* tp_repr */
	0,											   /* tp_as_number */
	0,											   /* tp_as_sequence */
	0,											   /* tp_as_mapping */
	0,											   /* tp_hash  */
	0,											   /* tp_call */
	0,											   /* tp_str */
	0,											   /* tp_getattro */
	0,											   /* tp_setattro */
	0,											   /* tp_as_buffer */
	Py_TPFLAGS_DEFAULT,							  /* tp_flags */
	"type of the update proxy",					  /* tp_doc */
	0,											   /* tp_traverse */
	0,											   /* tp_clear */
	0,											   /* tp_richcompare */
	0,											   /* tp_weaklistoffset */
	0,											   /* tp_iter */
	0,											   /* tp_iternext */
	0,											   /* tp_methods */
	0,											   /* tp_members */
	0,											   /* tp_getset */
	0,											   /* tp_base */
	0,											   /* tp_dict */
	snakeoil_protectedset_contains_descr,			/* tp_descr_get */
	0,											   /* tp_descr_set */
};


PyDoc_STRVAR(
	snakeoil_klass_documentation,
	"misc cpython class functionality");


PyMODINIT_FUNC
init_klass(void)
{
	PyObject *m = Py_InitModule3("_klass", NULL, snakeoil_klass_documentation);
	if (!m)
		return;

	if (PyType_Ready(&snakeoil_GetAttrProxyType) < 0)
		return;

	if (PyType_Ready(&snakeoil_ReflectiveHashType) < 0)
		return;

	if (PyType_Ready(&snakeoil_InternalJitAttrType) < 0)
		return;

	if (PyType_Ready(&snakeoil_GetType) < 0)
		return;

	if (PyType_Ready(&snakeoil_ContainsType) < 0)
		return;

	if (PyType_Ready(&snakeoil_AttrGetItemType) < 0)
		return;

	if (PyType_Ready(&snakeoil_AttrSetItemType) < 0)
		return;

	if (PyType_Ready(&snakeoil_AttrDelItemSlowType) < 0)
		return;

	if (PyType_Ready(&snakeoil_AttrDelItemFastType) < 0)
		return;

	if (PyType_Ready(&snakeoil_AttrContainsType) < 0)
		return;

	if (PyType_Ready(&snakeoil_AttrPopType) < 0)
		return;

	if (PyType_Ready(&snakeoil_AttrGetType) < 0)
		return;

	if (PyType_Ready(&snakeoil_AttrUpdateType) < 0)
		return;

	if (PyType_Ready(&snakeoil_ProtectedSetContainsType) < 0)
		return;

	if (PyType_Ready(&snakeoil_generic_equality_eq_type) < 0)
		return;

	if (PyType_Ready(&snakeoil_generic_equality_ne_type) < 0)
		return;

	snakeoil_LOAD_STRING(snakeoil_equality_attr, "__attr_comparison__");
	snakeoil_LOAD_STRING(snakeoil__orig_attr, "_orig");
	snakeoil_LOAD_STRING(snakeoil__new_attr, "_new");


#define ADD_TYPE_INSTANCE(type_ptr, name)				\
{														\
	PyObject *tmp;										\
	if (!(tmp = PyType_GenericNew((type_ptr), NULL, NULL))) \
		return;											\
	if (PyModule_AddObject(m, name, tmp) == -1)			\
		return;											\
}

	ADD_TYPE_INSTANCE(&snakeoil_GetType, "get");
	ADD_TYPE_INSTANCE(&snakeoil_ContainsType, "contains");
	ADD_TYPE_INSTANCE(&snakeoil_AttrGetItemType, "attr_getitem");
	ADD_TYPE_INSTANCE(&snakeoil_AttrSetItemType, "attr_setitem");
	ADD_TYPE_INSTANCE(&snakeoil_AttrDelItemSlowType, "attr_delitem_slow");
	ADD_TYPE_INSTANCE(&snakeoil_AttrDelItemFastType, "attr_delitem_fast");
	ADD_TYPE_INSTANCE(&snakeoil_AttrContainsType, "attr_contains");
	ADD_TYPE_INSTANCE(&snakeoil_AttrPopType, "attr_pop");
	ADD_TYPE_INSTANCE(&snakeoil_AttrGetType, "attr_get");
	ADD_TYPE_INSTANCE(&snakeoil_AttrUpdateType, "attr_update");
	ADD_TYPE_INSTANCE(&snakeoil_ProtectedSetContainsType, "ProtectedSet_contains");
	ADD_TYPE_INSTANCE(&snakeoil_generic_equality_eq_type, "generic_eq");
	ADD_TYPE_INSTANCE(&snakeoil_generic_equality_ne_type, "generic_ne");

#undef ADD_TYPE_INSTANCE

	Py_INCREF(&snakeoil_GetAttrProxyType);
	if (PyModule_AddObject(
			m, "GetAttrProxy", (PyObject *)&snakeoil_GetAttrProxyType) == -1)
		return;

	Py_INCREF(&snakeoil_ReflectiveHashType);
	if (PyModule_AddObject(
			m, "reflective_hash", (PyObject *)&snakeoil_ReflectiveHashType) == -1)
		return;

	Py_INCREF(&snakeoil_InternalJitAttrType);
	if (PyModule_AddObject(
			m, "_internal_jit_attr", (PyObject *)&snakeoil_InternalJitAttrType) == -1)
		return;
}
