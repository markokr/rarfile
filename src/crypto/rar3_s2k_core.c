/*
 * rar3_s2k_core in C.
 */

#include <Python.h>

#include "bhash.h"
#include "rar3_s2k_core.h"

static inline uint32_t load_be32(const uint8_t *p)
{
	return (uint32_t)(p[0]) << 24 |
	    (uint32_t)(p[1]) << 16 | (uint32_t)(p[2]) << 8 | (uint32_t)(p[3]);
}

static inline void store_le32(uint8_t *p, uint32_t x)
{
	p[0] = x & 0xFF;
	p[1] = (x >> 8) & 0xFF;
	p[2] = (x >> 16) & 0xFF;
	p[3] = (x >> 24) & 0xFF;
}

static bool validate_digest(PyObject *d)
{
	if (!PyBytes_Check(d) || PyBytes_Size(d) != 20) {
		PyErr_SetString(PyExc_ValueError, "digest() returned invalid result");
		return false;
	}
	return true;
}

/* unrolled message schedule calculation */
#define WBUF 16
#define W(i) w[(i) & (WBUF-1)]
#define P(i) p[((i) & 15) * 4]
#define R1(_i) \
	do { \
		unsigned int i = _i; \
		if (i < 16) { \
			W(i) = load_be32(&P(i)); \
		} else { \
			uint32_t x = W(i - 3) ^ W(i - 8) ^ W(i - 14) ^ W(i - 16); \
			W(i) = (x << 1) | (x >> 31); \
		} \
		if (i >= 64) { \
			store_le32(&P(i), W(i)); \
		} \
	} while (0)
#define R4(i) R1(i); R1(i + 1); R1(i + 2); R1(i + 3)
#define R16(i) R4(i); R4(i + 4); R4(i + 8); R4(i + 12)
#define R64(i) R16(i); R16(i + 16); R16(i + 32); R16(i + 48)
#define R80(i) R16(i); R64(i + 16)

static void rar3_corrupt_block(uint8_t *p)
{
	uint32_t w[WBUF];

	R80(0);
}

static PyObject *process_final_key(struct BufferedHash *buf)
{
	uint8_t key[16];

	PyObject *d = bhash_digest(buf);
	if (!d || !validate_digest(d)) {
		Py_XDECREF(d);
		return NULL;
	}
	const uint8_t *bytes = (uint8_t *)PyBytes_AsString(d);

	/* swap byte order */
	for (int i = 0; i < 4; i++) {
		store_le32(&key[i * 4], load_be32(&bytes[i * 4]));
	}

	Py_DECREF(d);
	return PyBytes_FromStringAndSize((char *)key, 16);
}

PyObject *rar3_s2k_core(PyObject *self, PyObject *seed)
{
	struct BufferedHash buf = BHASH_NULL;
	uint32_t count = 0;
	uint8_t ivbuf[16] = { 0 };

	PyObject *seed_buf = PyByteArray_FromObject(seed);
	if (seed_buf == NULL)
		return NULL;
	uint8_t *seed_ptr = (uint8_t *)PyByteArray_AsString(seed_buf);
	size_t seed_len = (size_t)PyByteArray_Size(seed_buf);

	if (!bhash_init(&buf, "sha1")) {
		Py_DECREF(seed_buf);
		return NULL;
	}

	for (int i = 0; i < 16; i++) {
		for (int j = 0; j < 0x4000; j++, count++) {
			size_t sha1pos = buf.nbytes & 63;

			/* add seed */
			if (!bhash_update(&buf, seed_ptr, seed_len))
				goto error;

			/* add 3-byte count */
			uint8_t count_buf[4];
			store_le32(count_buf, count);
			if (!bhash_update(&buf, count_buf, 3))
				goto error;

			/* Corrupt 64-byte blocks that land inside seed */
			if (seed_len > 64) {
				size_t dpos = 64 - sha1pos;
				while (dpos + 64 <= seed_len) {
					rar3_corrupt_block(seed_ptr + dpos);
					dpos += 64;
				}
			}

			/* Collect IV */
			if (j == 0) {
				PyObject *d = bhash_digest(&buf);
				if (!d || !validate_digest(d)) {
					Py_XDECREF(d);
					goto error;
				}
				ivbuf[i] = (uint8_t)PyBytes_AsString(d)[19];
				Py_DECREF(d);
			}
		}
	}

	PyObject *key = process_final_key(&buf);
	bhash_free(&buf);
	Py_DECREF(seed_buf);
	if (key == NULL)
		return NULL;

	PyObject *iv = PyBytes_FromStringAndSize((char *)ivbuf, 16);
	if (iv == NULL) {
		Py_DECREF(key);
		return NULL;
	}

	PyObject *result = PyTuple_Pack(2, key, iv);
	Py_DECREF(key);
	Py_DECREF(iv);
	return result;

 error:
	bhash_free(&buf);
	Py_DECREF(seed_buf);
	return NULL;
}
