/*
 * Python module setup.
 */

#include <Python.h>

#include "rar3_s2k_core.h"

static PyMethodDef crypto_methods[] = {
	{
	 "rar3_s2k_core",
	 rar3_s2k_core,
	 METH_O,
	 "rar3_s2k_core(seed) -> (key, iv)"},
	{NULL},
};

static PyModuleDef_Slot crypto_slots[] = {
#ifdef Py_GIL_DISABLED
	{Py_mod_gil, Py_MOD_GIL_NOT_USED},
#endif
	{0, NULL},
};

static struct PyModuleDef crypto_def = {
	.m_base = PyModuleDef_HEAD_INIT,
	.m_name = "_crypto",
	.m_doc = "Native accelerations for rarfile",
	.m_size = 0,
	.m_methods = crypto_methods,
	.m_slots = crypto_slots,
};

PyMODINIT_FUNC PyInit__crypto(void)
{
	return PyModuleDef_Init(&crypto_def);
}
