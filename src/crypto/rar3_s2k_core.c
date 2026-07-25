/*
 * rar3_s2k_core in C.
 */

#include <stdbool.h>

#include "module.h"

#define BHASH_BUFSIZE (1024)

struct BufferedHash {
	PyObject *update;
	PyObject *digest;
	size_t pos;
	size_t nbytes;
	unsigned char data[BHASH_BUFSIZE];
};

#define BHASH_NULL { NULL, NULL }

static bool bhash_init(struct BufferedHash *buf, PyObject *ctx)
{
	PyObject *update = PyObject_GetAttrString(ctx, "update");
	if (!update)
		return false;
	PyObject *digest = PyObject_GetAttrString(ctx, "digest");
	if (!digest) {
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

static bool bhash_update(struct BufferedHash *buf, const unsigned char *data, size_t size)
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

static PyObject *bhash_digest(struct BufferedHash *buf)
{
	if (!bhash_flush(buf))
		return NULL;
	return PyObject_CallFunctionObjArgs(buf->digest, NULL);
}

static void bhash_free(struct BufferedHash *buf)
{
	Py_XDECREF(buf->update);
	Py_XDECREF(buf->digest);
	buf->update = NULL;
	buf->digest = NULL;
}

/* unrolled message schedule calcuation */
#define R1(w, _i) do { \
	int i = _i; \
        uint32_t x = w[(i - 3) & 15] ^ w[(i - 8) & 15] ^ w[(i - 14) & 15] ^ w[(i - 16) & 15]; \
	w[i & 15] = (x << 1) | (x >> 31); \
} while (0)
#define R4(w, i) R1(w, i); R1(w, i + 1); R1(w, i + 2); R1(w, i + 3)
#define R16(w, i) R4(w, i); R4(w, i + 4); R4(w, i + 8); R4(w, i + 12)
#define R64(w, i) R16(w, i); R16(w, i + 16); R16(w, i + 32); R16(w, i + 48)

static inline uint32_t load_be32(const unsigned char *p)
{
	return (uint32_t) (p[0]) << 24 |
	    (uint32_t) (p[1]) << 16 | (uint32_t) (p[2]) << 8 | (uint32_t) (p[3]);
}

static inline void store_le32(unsigned char *p, uint32_t x)
{
	p[0] = x & 0xFF;
	p[1] = (x >> 8) & 0xFF;
	p[2] = (x >> 16) & 0xFF;
	p[3] = (x >> 24) & 0xFF;
}

static void rar3_corrupt_block(unsigned char *p)
{
	uint32_t w[16];

	for (int i = 0; i < 16; i++) {
		w[i] = load_be32(&p[i * 4]);
	}

	/* unrolled rounds 16..79 */
	R64(w, 16);

	for (int i = 0; i < 16; i++) {
		store_le32(&p[i * 4], w[i]);
	}
}

PyObject *rar3_s2k_core(PyObject *self, PyObject *seed)
{
	PyObject *sha1 = NULL;
	PyObject *hashlib = NULL;
	struct BufferedHash buf = BHASH_NULL;
	uint32_t count = 0;
	unsigned char ivbuf[16] = { 0 };

	/* seed must be a bytearray so we can mutate it in place */
	if (!PyByteArray_Check(seed)) {
		PyErr_SetString(PyExc_TypeError, "seed must be a bytearray");
		return NULL;
	}
	unsigned char *seed_ptr = (unsigned char *)PyByteArray_AsString(seed);
	Py_ssize_t seed_len = PyByteArray_Size(seed);

	hashlib = PyImport_ImportModule("hashlib");
	if (!hashlib)
		goto error;
	sha1 = PyObject_CallMethod(hashlib, "sha1", NULL);
	Py_CLEAR(hashlib);
	if (!sha1)
		goto error;

	if (!bhash_init(&buf, sha1))
		goto error;

	for (unsigned int i = 0; i < 16; i++) {
		for (unsigned int j = 0; j < 0x4000; j++, count++) {
			size_t sha1pos = buf.nbytes & 63;

			/* add seed */
			if (!bhash_update(&buf, seed_ptr, seed_len))
				goto error;

			/* add 3-byte count */
			unsigned char count_buf[4];
			store_le32(count_buf, count);
			if (!bhash_update(&buf, count_buf, 3))
				goto error;

			/* Corrupt 64-byte blocks that land inside seed */
			if (seed_len > 64) {
				size_t dpos = 64 - sha1pos;
				while (dpos + 64 <= (size_t)seed_len) {
					rar3_corrupt_block(seed_ptr + dpos);
					dpos += 64;
				}
			}

			/* Collect IV */
			if (j == 0) {
				PyObject *d = bhash_digest(&buf);
				if (!d)
					goto error;

				if (!PyBytes_Check(d) || PyBytes_Size(d) != 20) {
					Py_DECREF(d);
					PyErr_SetString(PyExc_RuntimeError,
							"digest() did not return SHA1 bytes");
					goto error;
				}

				ivbuf[i] = (unsigned char)PyBytes_AsString(d)[19];
				Py_DECREF(d);
			}
		}
	}
	if (!bhash_flush(&buf))
		goto error;

	PyObject *iv = PyBytes_FromStringAndSize((char *)ivbuf, 16);
	if (!iv)
		goto error;

	PyObject *result = PyTuple_Pack(2, sha1, iv);
	Py_DECREF(sha1);
	Py_DECREF(iv);
	bhash_free(&buf);
	return result;

 error:
	Py_XDECREF(hashlib);
	Py_XDECREF(sha1);
	bhash_free(&buf);
	return NULL;
}
