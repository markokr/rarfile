/*
 * Python module setup.
 */

#include <Python.h>

#include "module.h"
#include "rar3_s2k_core.h"

static PyMethodDef crypto_methods[] = {
	{
	 "rar3_s2k_core",
	 rar3_s2k_core,
	 METH_O,
	 "rar3_s2k_core(seed) -> (key, iv)"},
	{NULL},
};

static int crypto_exec(PyObject *module)
{
	struct crypto_state *st = PyModule_GetState(module);
	if (st == NULL)
		return -1;

	PyObject *hashlib = PyImport_ImportModule("hashlib");
	if (hashlib == NULL)
		return -1;

	st->sha1 = PyObject_GetAttrString(hashlib, "sha1");
	Py_DECREF(hashlib);
	if (st->sha1 == NULL)
		return -1;

	return 0;
}

static int crypto_traverse(PyObject *module, visitproc visit, void *arg)
{
	struct crypto_state *st = PyModule_GetState(module);
	if (st != NULL) {
		Py_VISIT(st->sha1);
	}
	return 0;
}

static int crypto_clear(PyObject *module)
{
	struct crypto_state *st = PyModule_GetState(module);
	if (st != NULL) {
		Py_CLEAR(st->sha1);
	}
	return 0;
}

static void crypto_free(void *module)
{
	PyObject *m = module;
	crypto_clear(m);
}

static PyModuleDef_Slot crypto_slots[] = {
	{Py_mod_exec, crypto_exec},
#ifdef Py_MOD_PER_INTERPRETER_GIL_SUPPORTED
	{Py_mod_multiple_interpreters, Py_MOD_PER_INTERPRETER_GIL_SUPPORTED},
#endif
#ifdef Py_GIL_DISABLED
	{Py_mod_gil, Py_MOD_GIL_NOT_USED},
#endif
	{0, NULL},
};

static struct PyModuleDef crypto_def = {
	.m_base = PyModuleDef_HEAD_INIT,
	.m_name = "_crypto",
	.m_doc = "Native accelerations for rarfile",
	.m_size = sizeof(struct crypto_state),
	.m_methods = crypto_methods,
	.m_slots = crypto_slots,
	.m_traverse = crypto_traverse,
	.m_clear = crypto_clear,
	.m_free = crypto_free,
};

PyMODINIT_FUNC PyInit__crypto(void)
{
	return PyModuleDef_Init(&crypto_def);
}
