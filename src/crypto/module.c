/*
 * Python module setup.
 */

#include "module.h"

static PyMethodDef crypto_methods[] = {
	{
	 "rar3_s2k_core",
	 rar3_s2k_core,
	 METH_O,
	 "rar3_s2k_core(seed) -> (sha1, iv)"},
	{NULL},
};

static struct PyModuleDef crypto_def = {
	.m_base = PyModuleDef_HEAD_INIT,
	.m_name = "_crypto",
	.m_doc = "Native accelerations for rarfile",
	.m_size = -1,
	.m_methods = crypto_methods,
};

PyMODINIT_FUNC PyInit__crypto(void)
{
	PyObject *m = PyModule_Create(&crypto_def);
	if (m == NULL) {
		return NULL;
	}
#ifdef Py_GIL_DISABLED
	PyUnstable_Module_SetGIL(m, Py_MOD_GIL_NOT_USED);
#endif
	return m;
}
