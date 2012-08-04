/*
 * Copyright: 2012 Brian Harring <ferringb@gmail.com>
 * License: BSD/GPL2
 *
 * C version of core whirlpool functionality for speed reasons.
 */

#define PY_SSIZE_T_CLEAN

#include "snakeoil/common.h"

static unsigned long long C0[256];
static unsigned long long C1[256];
static unsigned long long C2[256];
static unsigned long long C3[256];
static unsigned long long C4[256];
static unsigned long long C5[256];
static unsigned long long C6[256];
static unsigned long long C7[256];
static int is_initialized = 0;


static PyObject *
snakeoil_whirlpool_CDo(PyObject *self, PyObject *args)
{
	if(!is_initialized) {
		PyErr_SetString(PyExc_RuntimeError, "whirlpool internals not initialized");
		return NULL;
	}

	/* Relevant python code: 
	def CDo(buf, a0, a1, a2, a3, a4, a5, a6, a7):
		return C0[((buf[a0] >> 56) % 0x100000000) & 0xff] ^ \
		C1[((buf[a1] >> 48) % 0x100000000) & 0xff] ^ \
		C2[((buf[a2] >> 40) % 0x100000000) & 0xff] ^ \
		C3[((buf[a3] >> 32) % 0x100000000) & 0xff] ^ \
		C4[((buf[a4] >> 24) % 0x100000000) & 0xff] ^ \
		C5[((buf[a5] >> 16) % 0x100000000) & 0xff] ^ \
		C6[((buf[a6] >>  8) % 0x100000000) & 0xff] ^ \
		C7[((buf[a7] >>  0) % 0x100000000) & 0xff]
	*/

	PyObject *tmp;
	int a0, a1, a2, a3, a4, a5, a6, a7;
	if (!PyArg_ParseTuple(args, "Oiiiiiiii", &tmp, &a0, &a1, &a2, &a3,
						  &a4, &a5, &a6, &a7)) {
		return NULL;
	}
	if (!PyList_CheckExact(tmp) && !PyTuple_CheckExact(tmp)) {
		PyErr_SetString(PyExc_RuntimeError,
			"isinstance(val, (str, tuple, list)) failed");
		return NULL;
	} else if (PySequence_Fast_GET_SIZE(tmp) < 8) {
		PyErr_SetString(PyExc_RuntimeError,
			"passed in item is less than 8 items in length");
		return NULL;
	}

	unsigned long long result = 0, val;
	PyObject **items = PySequence_Fast_ITEMS(tmp);
	PyErr_Clear();
	#define CDo_item(array, index, shift) \
		if (PyInt_CheckExact(items[(index)])) { \
			val = (unsigned long long)PyInt_AS_LONG(items[(index)]); \
		} else { \
			val = PyLong_AsUnsignedLongLong(items[(index)]); \
			if (val == -1 && PyErr_Occurred()) { \
				return NULL; \
			} \
		} \
		result ^= ((array)[(val >> (shift)) & 0xff]);
	CDo_item(C0, a0, 56);
	CDo_item(C1, a1, 48);
	CDo_item(C2, a2, 40);
	CDo_item(C3, a3, 32);
	CDo_item(C4, a4, 24);
	CDo_item(C5, a5, 16);
	CDo_item(C6, a6, 8);
	CDo_item(C7, a7, 0);
	#undef CDo_item
	return PyLong_FromUnsignedLongLong(result);
		
}


static int
snakeoil_whirlpool_init_hash(PyObject *source, unsigned long long hash[])
{
	if (PySequence_Length(source) != 256) {
		PyErr_SetString(PyExc_RuntimeError, "whirlpool init: had non 256 length constant");
		return 1;
	}
	PyObject *tmp = NULL;
	Py_ssize_t x;
	PyErr_Clear();
	for (x = 0; x < 256; x++) {
		if (!(tmp = PySequence_GetItem(source, x))) {
			return 0;
		}
		tmp = PyNumber_Long(tmp);
		if (!tmp) {
			return 0;
		}
		hash[x] = PyLong_AsUnsignedLongLong(tmp);
		if (hash[x] == -1 && PyErr_Occurred()) {
			return 0;
		}
	}		
	return 1;
}

static PyObject *
snakeoil_whirlpool_init(PyObject *self, PyObject *args)
{
	PyObject *pc0, *pc1, *pc2, *pc3, *pc4, *pc5, *pc6, *pc7;
	if (!PyArg_ParseTuple(args, "OOOOOOOO", &pc0, &pc1, &pc2, &pc3,
						  &pc4, &pc5, &pc6, &pc7)) {
		return NULL;
	}
	#define init_hash(source, target) \
	if (!snakeoil_whirlpool_init_hash((source), (target))) { \
		return NULL; \
	}
	init_hash(pc0, C0);
	init_hash(pc1, C1);
	init_hash(pc2, C2);
	init_hash(pc3, C3);
	init_hash(pc4, C4);
	init_hash(pc5, C5);
	init_hash(pc6, C6);
	init_hash(pc7, C7);
	#undef init_hash
	is_initialized = 1;
	Py_RETURN_TRUE;
}


/* Module setup */
static PyMethodDef snakeoil_whirlpool_methods[] = {
	{"init", (PyCFunction)snakeoil_whirlpool_init, METH_VARARGS,
	 "init(C0, C1, C2, C3, C4, C5, C6, C7)"},
	{"CDo", (PyCFunction)snakeoil_whirlpool_CDo, METH_VARARGS,
	 "CDo(buf, a0, a1, a2, a3, a4, a5, a6, a7)"},
	{NULL}
};


PyDoc_STRVAR(
	snakeoil_whirlpool_documentation,
	"C extension to optimize whirlpools CDo core function");


PyMODINIT_FUNC
init_whirlpool_cdo(void)
{
	PyObject *m;
	m = Py_InitModule3("_whirlpool_cdo", snakeoil_whirlpool_methods,
					  snakeoil_whirlpool_documentation);
}
	
