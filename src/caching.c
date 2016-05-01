/*
 * Copyright: 2006-2011 Brian Harring <ferringb@gmail.com>
 * Copyright: 2006 Marien Zwart <marienz@gentoo.org>
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

static PyObject *snakeoil_caching_disable_str = NULL;

/*
 * WeakValFinalizer: holds a reference to a dict and key,
 * does "del dict[key]" when called. Used as weakref callback.
 * Only used internally (does not expose a constructor/new method).
 *
 * Together with a "normal" PyDict this is used as a much more minimal
 * version of python's weakref.WeakValueDictionary. One noticable
 * difference between that and this is that WeakValueDictionary gives
 * the weakref callbacks responsible for removing an item from the
 * dict a weakref to the dict, while we use a "hard" reference to it.
 *
 * WeakValueDictionary has to do it that way to prevent objects in the
 * dict from keeping the dict alive. That should not be an issue here:
 * the objects in the dict have a hard reference to the dict through
 * their type anyway. So this simplifies things a bit (especially
 * since you cannot weakref a PyDict, it would have to be subclassed
 * to add that ability (WeakValueDictionary is a UserDict, not a
 * "real" dict, so it does not have that problem)).
 */

typedef struct {
	PyObject_HEAD
	PyObject *dict;
	PyObject *key;
} snakeoil_WeakValFinalizer;

static void
snakeoil_WeakValFinalizer_dealloc(snakeoil_WeakValFinalizer *self)
{
	Py_CLEAR(self->dict);
	Py_CLEAR(self->key);
	self->ob_type->tp_free((PyObject*) self);
}

static PyObject *
snakeoil_WeakValFinalizer_call(snakeoil_WeakValFinalizer *self,
	PyObject *args, PyObject *kwargs)
{
	/* We completely ignore whatever arguments are passed to us
	   (should be a single positional (the weakref) we do not need). */
	if (PyDict_DelItem(self->dict, self->key) < 0)
		return NULL;
	Py_RETURN_NONE;
}

static int
snakeoil_WeakValFinalizer_traverse(
	snakeoil_WeakValFinalizer *self, visitproc visit, void *arg)
{
	Py_VISIT(self->dict);
	Py_VISIT(self->key);
	return 0;
}

static int
snakeoil_WeakValFinalizer_heapyrelate(NyHeapRelate *r)
{
	snakeoil_WeakValFinalizer *v = (snakeoil_WeakValFinalizer*)r->src;
	INTERATTR(dict);
	INTERATTR(key);
	return 0;
}

static PyTypeObject snakeoil_WeakValFinalizerType = {
	PyObject_HEAD_INIT(NULL)
	0,											   /* ob_size */
	"snakeoil._caching.WeakValFinalizer",			/* tp_name */
	sizeof(snakeoil_WeakValFinalizer),				/* tp_basicsize */
	0,											   /* tp_itemsize */
	(destructor)snakeoil_WeakValFinalizer_dealloc,	/* tp_dealloc */
	0,											   /* tp_print */
	0,											   /* tp_getattr */
	0,											   /* tp_setattr */
	0,											   /* tp_compare */
	0,											   /* tp_repr */
	0,											   /* tp_as_number */
	0,											   /* tp_as_sequence */
	0,											   /* tp_as_mapping */
	0,											   /* tp_hash  */
	(ternaryfunc)snakeoil_WeakValFinalizer_call,	  /* tp_call */
	(reprfunc)0,									 /* tp_str */
	0,											   /* tp_getattro */
	0,											   /* tp_setattro */
	0,											   /* tp_as_buffer */
	Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,		 /* tp_flags */
	"WeakValFinalizer objects",					  /* tp_doc */
	(traverseproc)snakeoil_WeakValFinalizer_traverse, /* tp_traverse */
};

static snakeoil_WeakValFinalizer *
snakeoil_WeakValFinalizer_create(PyObject *dict, PyObject *key)
{
	snakeoil_WeakValFinalizer *finalizer = PyObject_GC_New(
		snakeoil_WeakValFinalizer, &snakeoil_WeakValFinalizerType);

	if (!finalizer)
		return NULL;

	Py_INCREF(dict);
	finalizer->dict = dict;
	Py_INCREF(key);
	finalizer->key = key;

	PyObject_GC_Track(finalizer);

	return finalizer;
}

typedef struct {
	PyObject_HEAD
	PyObject *dict;
} snakeoil_WeakValCache;

static PyObject *
snakeoil_WeakValCache_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	snakeoil_WeakValCache *self;
	self = (snakeoil_WeakValCache *)type->tp_alloc(type, 0);
	if (!self)
		return NULL;
	self->dict = PyDict_New();
	if (!self->dict) {
		Py_DECREF(self);
		return NULL;
	}
	return (PyObject *)self;
}

static int
snakeoil_WeakValCache_traverse(
	snakeoil_WeakValCache *self, visitproc visit, void *arg)
{
	Py_VISIT(self->dict);
	return 0;
}

static int
snakeoil_WeakValCache_heapyrelate(NyHeapRelate *r)
{
	snakeoil_WeakValCache *v = (snakeoil_WeakValCache*) r->src;
	INTERATTR(dict);
	return 0;
}

static PyObject *
snakeoil_WeakValCache_keys(snakeoil_WeakValCache *self)
{
	return PyDict_Keys(self->dict);
}

static PyObject *
snakeoil_WeakValCache_values(snakeoil_WeakValCache *self)
{
	return PyDict_Values(self->dict);
}

static PyObject *
snakeoil_WeakValCache_items(snakeoil_WeakValCache *self)
{
	return PyDict_Items(self->dict);
}

static int
snakeoil_WeakValCache_clear(snakeoil_WeakValCache *self)
{
	PyDict_Clear(self->dict);
	return 0;
}

static PyObject *
snakeoil_WeakValCache_clear_method(snakeoil_WeakValCache *self)
{
	snakeoil_WeakValCache_clear(self);
	Py_RETURN_NONE;
}

static void
snakeoil_WeakValCache_dealloc(snakeoil_WeakValCache *self)
{
	Py_CLEAR(self->dict);
	self->ob_type->tp_free((PyObject *)self);
}

static Py_ssize_t
snakeoil_WeakValCache_len(snakeoil_WeakValCache *self)
{
	return PyDict_Size(self->dict);
}

static int
snakeoil_WeakValCache_setitem(snakeoil_WeakValCache *self, PyObject *key,
	PyObject *val)
{
	if (!val) {
		return PyDict_SetItem(self->dict, (PyObject*)key, (PyObject*)val);
	}
	if (PyWeakref_Check(val)) {
		PyErr_SetString(PyExc_TypeError, "cannot set value to a weakref");
		return -1;
	}

	int ret = -1;
	snakeoil_WeakValFinalizer *finalizer = snakeoil_WeakValFinalizer_create(
		self->dict, key);
	if (finalizer) {
		PyObject *weakref = PyWeakref_NewRef(val, (PyObject*)finalizer);
		Py_DECREF(finalizer);
		if (weakref) {
			ret = PyDict_SetItem(self->dict, key, (PyObject*)weakref);
			Py_DECREF(weakref);
		}
	}
	return ret;
}

PyObject *
snakeoil_WeakValCache_getitem(snakeoil_WeakValCache *self, PyObject *key)
{
	PyObject *resobj, *actual = NULL;
	resobj = PyDict_GetItem(self->dict, key);
	if (resobj) {
		actual = PyWeakref_GetObject(resobj);
		if (actual == Py_None) {
			// PyWeakref_GetObject returns a borrowed reference, do not
			// clear it
			actual = NULL;
			if (-1 == PyDict_DelItem(self->dict, key)) {
				return NULL;
			}
		} else {
			Py_INCREF(actual);
		}
	} else {
		PyErr_SetObject(PyExc_KeyError, key);
	}
	return actual;
}

static PyObject *
snakeoil_WeakValCache_get(snakeoil_WeakValCache *self, PyObject *args)
{
	Py_ssize_t size = PyTuple_Size(args);
	if (-1 == size)
		return NULL;
	PyObject *key, *resobj;
	if (size < 1 || size > 2) {
		PyErr_SetString(PyExc_TypeError,
			"get requires one arg (key), with optional default to return");
		return NULL;
	}
	key = PyTuple_GET_ITEM(args, 0);
	if (!key) {
		return NULL;
	}

	resobj = PyObject_GetItem((PyObject *)self, key);
	if (resobj) {
		return resobj;

	} else if (PyErr_Occurred() && !PyErr_ExceptionMatches(PyExc_KeyError)) {
		// if the error wasn't that the key isn't found, return
		return NULL;
	}

	PyErr_Clear();
	if (size == 2) {
		resobj = PyTuple_GET_ITEM(args, 1);
	} else {
		resobj = Py_None;
	}
	Py_INCREF(resobj);
	return resobj;
}

static PyMappingMethods snakeoil_WeakValCache_as_mapping = {
	(lenfunc)snakeoil_WeakValCache_len,			   /* len() */
	(binaryfunc)snakeoil_WeakValCache_getitem,		/* getitem */
	(objobjargproc)snakeoil_WeakValCache_setitem,	 /* setitem */
};


static PyMethodDef snakeoil_WeakValCache_methods[] = {
	{"keys", (PyCFunction)snakeoil_WeakValCache_keys, METH_NOARGS,
		"keys()"},
	{"values", (PyCFunction)snakeoil_WeakValCache_values, METH_NOARGS,
		"values()"},
	{"items", (PyCFunction)snakeoil_WeakValCache_items, METH_NOARGS,
		"items()"},
	{"get", (PyCFunction)snakeoil_WeakValCache_get, METH_VARARGS,
		"get(key, default=None)"},
	{"clear", (PyCFunction)snakeoil_WeakValCache_clear_method, METH_NOARGS,
		"clear()"},
	{NULL}
};

/* WeakValCache; simplified WeakValDictionary. */

static PyTypeObject snakeoil_WeakValCacheType = {
	PyObject_HEAD_INIT(NULL)
	0,											   /* ob_size */
	"snakeoil._caching.WeakValCache",				/* tp_name */
	sizeof(snakeoil_WeakValCache),					/* tp_basicsize */
	0,											   /* tp_itemsize */
	(destructor)snakeoil_WeakValCache_dealloc,		/* tp_dealloc */
	0,											   /* tp_print */
	0,											   /* tp_getattr */
	0,											   /* tp_setattr */
	0,											   /* tp_compare */
	0,											   /* tp_repr */
	0,											   /* tp_as_number */
	0,											   /* tp_as_sequence */
	&snakeoil_WeakValCache_as_mapping,				/* tp_as_mapping */
	0,											   /* tp_hash  */
	0,											   /* tp_call */
	(reprfunc)0,									 /* tp_str */
	0,											   /* tp_getattro */
	0,											   /* tp_setattro */
	0,											   /* tp_as_buffer */
	Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,		 /* tp_flags */
	0,											   /* tp_doc */
	(traverseproc)snakeoil_WeakValCache_traverse,	 /* tp_traverse */
	(inquiry)snakeoil_WeakValCache_clear,			 /* tp_clear */
	0,											   /* tp_richcompare */
	0,											   /* tp_weaklistoffset */
	0,											   /* tp_iter */
	0,											   /* tp_iternext */
	snakeoil_WeakValCache_methods,					/* tp_methods */
	0,											   /* tp_members */
	0,											   /* tp_getset */
	0,											   /* tp_base */
	0,											   /* tp_dict */
	0,											   /* tp_descr_get */
	0,											   /* tp_descr_set */
	0,											   /* tp_dictoffset */
	0,											   /* tp_init */
	0,											   /* tp_alloc */
	snakeoil_WeakValCache_new,						/* tp_new */
};


/* WeakInstMeta: metaclass for instance caching. */

typedef struct {
	PyHeapTypeObject type;
	PyObject *inst_dict;
	int inst_caching;
} snakeoil_WeakInstMeta;

static void
snakeoil_WeakInstMeta_dealloc(snakeoil_WeakInstMeta* self)
{
	Py_CLEAR(self->inst_dict);
	((PyObject*)self)->ob_type->tp_free((PyObject *)self);
}

static PyTypeObject snakeoil_WeakInstMetaType;

static PyObject *
snakeoil_WeakInstMeta_new(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
	const char *name;
	PyTupleObject *bases;
	PyObject *d;
	int inst_caching = 0;
	static char *kwlist[] = {"name", "bases", "dict", 0};

	if (!PyArg_ParseTupleAndKeywords(args, kwargs, "sO!O!", kwlist,
									 &name,
									 &PyTuple_Type, &bases,
									 &PyDict_Type, &d))
		return NULL;

	PyObject *cachesetting = PyMapping_GetItemString(d, "__inst_caching__");
	if (cachesetting) {
		inst_caching = PyObject_IsTrue(cachesetting);
		Py_DECREF(cachesetting);
		if (inst_caching < 0)
			return NULL;
	} else {
		if (!PyErr_ExceptionMatches(PyExc_KeyError))
			return NULL;
		PyErr_Clear();
	}
	if (PyDict_SetItemString(d, "__inst_caching__",
								inst_caching ? Py_True : Py_False) < 0)
		return NULL;

	if (inst_caching) {
		PyObject *slots = PyMapping_GetItemString(d, "__slots__");
		if (slots) {
			int has_weakref = 0;
			PyObject *base;
			int i, n = PyTuple_GET_SIZE(bases);
			for (i = 0; i < n; i++) {
				base = PyTuple_GET_ITEM(bases, i);
				if (PyObject_HasAttrString(base, "__weakref__")) {
					has_weakref = 1;
					break;
				}
			}
			if (!has_weakref) {
				PyObject *slottuple = Py_BuildValue("(s)", "__weakref__");
				if (!slottuple) {
					Py_DECREF(slots);
					return NULL;
				}
				PyObject *newslots = PySequence_Concat(slots, slottuple);
				Py_DECREF(slottuple);
				if (!newslots)
					return NULL;
				if (PyDict_SetItemString(d, "__slots__", newslots) < 0) {
					Py_DECREF(newslots);
					Py_DECREF(slots);
					return NULL;
				}
				Py_DECREF(newslots);
			}
			Py_DECREF(slots);
		} else {
			if (!PyErr_ExceptionMatches(PyExc_KeyError))
				return NULL;
			PyErr_Clear();
		}
	}

	snakeoil_WeakInstMeta *self;
	self = (snakeoil_WeakInstMeta*)PyType_Type.tp_new(type, args, kwargs);
	if (!self)
		return NULL;

	self->inst_caching = inst_caching;

	if (inst_caching) {
		if (!(self->inst_dict = PyDict_New())) {
			Py_DECREF((PyObject*)self);
			return NULL;
		}
	}
	return (PyObject*) self;
}


static PyObject *
snakeoil_WeakInstMeta_call(snakeoil_WeakInstMeta *self,
	PyObject *args, PyObject *kwargs)
{
	PyObject *key, *kwlist, *kwtuple, *resobj = NULL;
	int result;
	if (!self->inst_caching)
		/* No caching, just do what a "normal" type does */
		return PyType_Type.tp_call((PyObject*)self, args, kwargs);

	Py_ssize_t len = kwargs ? PyDict_Size(kwargs) : 0;
	if (len) {
		/* If disable_inst_caching=True is passed pop it and disable caching */
		PyObject *obj = PyDict_GetItem(kwargs, snakeoil_caching_disable_str);
		if (obj) {
			result = PyObject_IsTrue(obj);
			if (result < 0)
				return NULL;

			if (PyDict_DelItem(kwargs, snakeoil_caching_disable_str))
				return NULL;

			if (result)
				return PyType_Type.tp_call((PyObject*)self, args, kwargs);
		}
		/* Convert kwargs to a sorted tuple so we can hash it. */
		if (!(kwlist = PyDict_Items(kwargs)))
			return NULL;

		if (len > 1 && PyList_Sort(kwlist) < 0) {
			Py_DECREF(kwlist);
			return NULL;
		}

		kwtuple = PyList_AsTuple(kwlist);
		Py_DECREF(kwlist);
		if (!kwtuple)
			return NULL;
	} else {
		/* null kwargs is equivalent to a zero-length tuple */
		Py_INCREF(Py_None);
		kwtuple = Py_None;
	}

	/* Construct the dict key. Be careful not to leak this below! */
	key = PyTuple_Pack(2, args, kwtuple);
	Py_DECREF(kwtuple);
	if (!key)
		return NULL;

	// borrowed reference from PyDict_GetItem...
	resobj = PyDict_GetItem(self->inst_dict, key);

	if (resobj) {
		/* We have a weakref cached, return the value if it is still there */
		PyObject *actual = PyWeakref_GetObject(resobj);
		if (!actual) {
			Py_DECREF(key);
			return NULL;
		}
		if (actual != Py_None) {
			Py_INCREF(actual);
			Py_DECREF(key);
			return actual;
		}
		/* PyWeakref_GetObject returns a borrowed reference, do not clear it */
	}
	// if we got here, it's either not cached, or the key is unhashable.
	// we catch the unhashable when we try to save the key.

	resobj = PyType_Type.tp_call((PyObject*)self, args, kwargs);
	if (!resobj) {
		Py_DECREF(key);
		return NULL;
	}

	snakeoil_WeakValFinalizer *finalizer = snakeoil_WeakValFinalizer_create(
		self->inst_dict, key);
	if (!finalizer) {
		Py_DECREF(key);
		Py_DECREF(resobj);
		return NULL;
	}

	PyObject *weakref = PyWeakref_NewRef(resobj, (PyObject*)finalizer);
	Py_DECREF(finalizer);
	if (!weakref) {
		Py_DECREF(key);
		Py_DECREF(resobj);
		return NULL;
	}

	result = PyDict_SetItem(self->inst_dict, key, weakref);
	Py_DECREF(weakref);

	if (result < 0) {
		if (PyErr_ExceptionMatches(PyExc_TypeError) ||
			PyErr_ExceptionMatches(PyExc_NotImplementedError)) {
			PyErr_Clear();
			PyObject *format, *formatargs, *message;
			if ((format = PyString_FromString(
					"caching for %s, key=%s is unhashable"))) {
				if ((formatargs = PyTuple_Pack(2, self, key))) {
					if ((message = PyString_Format(format, formatargs))) {
						/* Leave resobj NULL if PyErr_Warn raises. */
						if (PyErr_Warn(
								PyExc_UserWarning,
								PyString_AsString(message))) {
							resobj = NULL;
						}
						Py_DECREF(message);
					}
					Py_DECREF(formatargs);
				}
				Py_DECREF(format);
			}
		} else {
			// unexpected exception... let it go.
			resobj = NULL;
		}
	}
	Py_DECREF(key);
	return resobj;
}


PyDoc_STRVAR(
	snakeoil_WeakInstMetaType__doc__,
	"metaclass for instance caching, resulting in reuse of unique instances.\n"
	"few notes-\n\n"
	"* instances must be immutable (or effectively so). Since creating a\n"
	"  new instance may return a preexisting instance, this requirement\n"
	"  B{must} be honored.\n"
	"* due to the potential for mishap, each subclass of a caching class \n"
	"  must assign __inst_caching__ = True to enable caching for the\n"
	"  derivative.\n"
	"* conversely, __inst_caching__ = False does nothing (although it's\n"
	"  useful as a sign of I{do not enable caching for this class}\n"
	"* instance caching can be disabled per instantiation via passing\n"
	"  disabling_inst_caching=True into the class constructor.\n"
	"\n"
	"Being a metaclass, the voodoo used doesn't require modification of the\n"
	"class itself.\n"
	"\n"
	"Examples of usage are the restriction modules\n"
	"L{packages<snakeoil.restrictions.packages>} and\n"
	"L{values<snakeoil.restrictions.values>}\n"
	);

static PyTypeObject snakeoil_WeakInstMetaType = {
	PyObject_HEAD_INIT(NULL)
	0,											   /* ob_size */
	"snakeoil._caching.WeakInstMeta",			/* tp_name */
	sizeof(snakeoil_WeakInstMeta),					/* tp_basicsize */
	0,											   /* tp_itemsize */
	/* methods */
	(destructor)snakeoil_WeakInstMeta_dealloc,		/* tp_dealloc */
	(printfunc)0,									/* tp_print */
	(getattrfunc)0,								  /* tp_getattr */
	(setattrfunc)0,								  /* tp_setattr */
	(cmpfunc)0,									  /* tp_compare */
	(reprfunc)0,									 /* tp_repr */
	0,											   /* tp_as_number */
	0,											   /* tp_as_sequence */
	0,											   /* tp_as_mapping */
	(hashfunc)0,									 /* tp_hash */
	(ternaryfunc)snakeoil_WeakInstMeta_call,		  /* tp_call */
	(reprfunc)0,									 /* tp_str */
	0,											   /* tp_getattro */
	0,											   /* tp_setattro */
	0,											   /* tp_as_buffer */
	Py_TPFLAGS_DEFAULT,							  /* tp_flags */
	snakeoil_WeakInstMetaType__doc__,				 /* tp_doc */
	(traverseproc)0,								 /* tp_traverse */
	(inquiry)0,									  /* tp_clear */
	(richcmpfunc)0,								  /* tp_richcompare */
	0,											   /* tp_weaklistoffset */
	(getiterfunc)0,								  /* tp_iter */
	(iternextfunc)0,								 /* tp_iternext */
	0,											   /* tp_methods */
	0,											   /* tp_members */
	0,											   /* tp_getset */
	&PyType_Type,                                  /* tp_base */
	0,											   /* tp_dict */
	0,											   /* tp_descr_get */
	0,											   /* tp_descr_set */
	0,											   /* tp_dictoffset */
	(initproc)0,									 /* tp_init */
	0,											   /* tp_alloc */
	snakeoil_WeakInstMeta_new,						/* tp_new */
};


static NyHeapDef snakeoil_caching_heapdefs[] = {
	{
		0,							/* flags */
		&snakeoil_WeakValFinalizerType, /* type */
		0,							/* size */
		0,							/* traverse */
		snakeoil_WeakValFinalizer_heapyrelate /* relate */
	},
	{
		0,							/* flags */
		&snakeoil_WeakValCacheType,	/* type */
		0,							/* size */
		0,							/* traverse */
		snakeoil_WeakValCache_heapyrelate /* relate */
	},
	{0}
};

/* Module initialization */

PyDoc_STRVAR(
	snakeoil_module_documentation,
	"C reimplementation of snakeoil.caching.");

PyMODINIT_FUNC
init_caching(void)
{
	/* Create the module and add the functions */
	PyObject *m = Py_InitModule3(
		"_caching", NULL, snakeoil_module_documentation);
	if (!m)
		return;

	if (PyType_Ready(&snakeoil_WeakInstMetaType) < 0)
		return;

	if (PyType_Ready(&snakeoil_WeakValCacheType) < 0)
		return;

	if (PyType_Ready(&snakeoil_WeakValFinalizerType) < 0)
		return;

	snakeoil_LOAD_STRING(snakeoil_caching_disable_str, "disable_inst_caching");

	Py_INCREF(&snakeoil_WeakInstMetaType);
	if (PyModule_AddObject(
			m, "WeakInstMeta", (PyObject *)&snakeoil_WeakInstMetaType) == -1)
		return;

	Py_INCREF(&snakeoil_WeakValCacheType);
	if (PyModule_AddObject(
			m, "WeakValCache", (PyObject *)&snakeoil_WeakValCacheType) == -1)
		return;

	PyObject *cobject = PyCObject_FromVoidPtrAndDesc(
		&snakeoil_caching_heapdefs, "NyHeapDef[] v1.0", 0);
	if (!cobject)
		return;

	if (PyModule_AddObject(m, "_NyHeapDefs_", cobject) == -1)
		return;

	/* Success! */
}
