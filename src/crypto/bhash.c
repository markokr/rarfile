/*
 * Buffered hash.
 */

#include <Python.h>

#include "bhash.h"

bool bhash_init(struct BufferedHash *buf, const char *algo)
{
	PyObject *hashlib = PyImport_ImportModule("hashlib");
	if (hashlib == NULL)
		return false;

	PyObject *ctx = PyObject_CallMethod(hashlib, algo, NULL);
	Py_DECREF(hashlib);
	if (ctx == NULL)
		return false;

	PyObject *update = PyObject_GetAttrString(ctx, "update");
	if (update == NULL) {
		Py_DECREF(ctx);
		return false;
	}

	PyObject *digest = PyObject_GetAttrString(ctx, "digest");
	Py_DECREF(ctx);
	if (digest == NULL) {
		Py_DECREF(update);
		return false;
	}
	buf->pos = buf->nbytes = 0;
	buf->update = update;
	buf->digest = digest;
	return true;
}

bool bhash_flush(struct BufferedHash *buf)
{
	if (buf->pos == 0)
		return true;

	PyObject *data = PyBytes_FromStringAndSize((const char *)buf->data, buf->pos);
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
