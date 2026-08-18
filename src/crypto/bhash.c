/*
 * Buffered hash.
 */

#include <Python.h>
#include <string.h>

#include "bhash.h"

/* bug in 3.10 stable ABI, PyMemoryView_FromMemory is 3.7+ */
#ifndef PyBUF_READ
#define PyBUF_READ 0x100
#endif

bool bhash_init(struct BufferedHash *buf, PyObject *ctx)
{
	PyObject *update = PyObject_GetAttrString(ctx, "update");
	if (update == NULL)
		return false;

	PyObject *digest = PyObject_GetAttrString(ctx, "digest");
	if (digest == NULL) {
		Py_DECREF(update);
		return false;
	}
	buf->pos = buf->nbytes = 0;
	buf->update = update;
	buf->digest = digest;
	return true;
}

static bool bhash_flush(struct BufferedHash *buf)
{
	if (buf->pos == 0)
		return true;

	PyObject *data = PyMemoryView_FromMemory((char *)buf->data, buf->pos, PyBUF_READ);
	if (data == NULL)
		return false;

	PyObject *result = PyObject_CallFunctionObjArgs(buf->update, data, NULL);
	Py_DECREF(data);
	if (result == NULL)
		return false;
	Py_DECREF(result);

	buf->pos = 0;
	return true;
}

bool bhash_update(struct BufferedHash *buf, const uint8_t *data, size_t size)
{
	size_t data_pos = 0;
	while (data_pos < size) {
		size_t avail = BHASH_BUFSIZE - buf->pos;
		size_t remain = size - data_pos;
		if (avail > 0) {
			size_t blk = avail > remain ? remain : avail;
			memcpy(buf->data + buf->pos, data + data_pos, blk);
			buf->nbytes += blk;
			buf->pos += blk;
			data_pos += blk;
		}
		if (buf->pos == BHASH_BUFSIZE) {
			if (!bhash_flush(buf))
				return false;
		}
	}
	return true;
}

PyObject *bhash_digest(struct BufferedHash *buf)
{
	if (!bhash_flush(buf))
		return NULL;
	return PyObject_CallFunctionObjArgs(buf->digest, NULL);
}

void bhash_free(struct BufferedHash *buf)
{
	Py_CLEAR(buf->update);
	Py_CLEAR(buf->digest);
}
