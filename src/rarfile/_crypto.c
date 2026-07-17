/*
* rarfile.py
#
* Copyright (c) 2005-2026  Marko Kreen <markokr@gmail.com>
#
* Permission to use, copy, modify, and/or distribute this software for any
* purpose with or without fee is hereby granted, provided that the above
* copyright notice and this permission notice appear in all copies.
#
* THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
* WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
* MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
* ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
* WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
* ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
* OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
*/

#include "_crypto.h"

/**
 * Emulate one block of the buggy RAR3 SHA1 corruption.
 *
 * Reads a 64-byte block as 16 big-endian words, runs the SHA1 message
 * schedule expansion (rounds 16..79) over a rolling 16-word window, then
 * writes the resulting words back little-endian, mutating the block in place.
 *
 * @param p pointer to a 64-byte block
 */
static void rar3_corrupt_block(unsigned char *p)
{
    uint32_t w[16];
    uint32_t x;
    int i;

    /* load big-endian */
    for (i = 0; i < 16; i++) {
        w[i] =
            (uint32_t)(p[i * 4 + 0]) << 24 |
            (uint32_t)(p[i * 4 + 1]) << 16 |
            (uint32_t)(p[i * 4 + 2]) << 8  |
            (uint32_t)(p[i * 4 + 3]);
    }

    for (i = 16; i < 80; i++) {
        x =
            w[(i - 3) & 15] ^
            w[(i - 8) & 15] ^
            w[(i - 14) & 15] ^
            w[(i - 16) & 15];

        w[i & 15] = (x << 1) | (x >> 31);
    }

    /* store little-endian */
    for (i = 0; i < 16; i++) {
        x = w[i];

        p[i*4+0] = x & 0xff;
        p[i*4+1] = (x >> 8) & 0xff;
        p[i*4+2] = (x >> 16) & 0xff;
        p[i*4+3] = (x >> 24) & 0xff;
    }
}

/**
 * Run the full RAR3 string-to-key hash (16 outer loops of 0x4000 iterations).
 *
 * Each iteration feeds `seed` and a 3-byte little-endian counter into the SHA1 `update`,
 * then corrupts `seed` in place for every full 64-byte block (the RAR3 bug).
 *
 * @param self
 * @param args (seed,)
 * @return (sha1, iv) tuple: the hashlib.sha1() object holding the final key
 *         state, and the 16-byte IV as a Python bytes object
 */
PyObject* rar3_sha1(PyObject *self, PyObject *args)
{
    PyObject *sha1 = NULL;
    PyObject *seed;
    PyObject *update = NULL;
    PyObject *digest = NULL;
    PyObject *hashlib = NULL;

    if (!PyArg_ParseTuple(args, "O", &seed))
        return NULL;

    /* writable view of the seed so we can emulate the in-place corruption */
    Py_buffer seed_view;
    if (PyObject_GetBuffer(seed, &seed_view, PyBUF_WRITABLE) < 0)
        return NULL;

    hashlib = PyImport_ImportModule("hashlib");
    if (!hashlib)
        goto error;
    sha1 = PyObject_CallMethod(hashlib, "sha1", NULL);
    Py_CLEAR(hashlib);
    if (!sha1)
        goto error;

    unsigned char *seed_ptr = (unsigned char *)seed_view.buf;
    Py_ssize_t seed_len = seed_view.len;

    char cnt[3];
    unsigned char iv[16] = {0};
    PyObject *result;
    PyObject *d;

    // Total bytes hashed so far
    unsigned long long nbytes = 0;

    update = PyObject_GetAttrString(sha1, "update");
    if (!update)
        goto error;
    digest = PyObject_GetAttrString(sha1, "digest");
    if (!digest)
        goto error;

    for (unsigned int i = 0; i < 16; ++i) {
        const unsigned int base = i << 14;

        for (unsigned int j = 0; j < 0x4000; ++j) {
            result = PyObject_CallFunctionObjArgs(update, seed, NULL);
            if (!result)
                goto error;
            Py_DECREF(result);

            // Corrupt each full 64-byte block that lands inside it (only when len(data) > 64)
            unsigned long bufpos = nbytes & 63;
            nbytes += (unsigned long long)(seed_len);
            if (seed_len > 64) {
                Py_ssize_t dpos = 64 - (Py_ssize_t)(bufpos);
                while (dpos + 64 <= seed_len) {
                    rar3_corrupt_block(seed_ptr + dpos);
                    dpos += 64;
                }
            }

            const unsigned int x = base + j;

            cnt[0] = x & 0xff;
            cnt[1] = (x >> 8) & 0xff;
            cnt[2] = (x >> 16) & 0xff;

            PyObject *pycnt = PyBytes_FromStringAndSize(cnt, 3);
            if (!pycnt)
                goto error;

            result = PyObject_CallFunctionObjArgs(update, pycnt, NULL);
            Py_DECREF(pycnt);
            if (!result)
                goto error;
            Py_DECREF(result);

            // counter is only 3 bytes, so it never triggers the corruption
            nbytes += 3;

            if (j == 0) {
                d = PyObject_CallFunctionObjArgs(digest, NULL);
                if (!d)
                    goto error;

                if (!PyBytes_Check(d) || PyBytes_Size(d) != 20)
                {
                    Py_DECREF(d);
                    PyErr_SetString(PyExc_RuntimeError, "digest() did not return SHA1 bytes");
                    goto error;
                }

                iv[i] = (unsigned char)PyBytes_AsString(d)[19];
                Py_DECREF(d);
            }
        }
    }

    Py_DECREF(update);
    Py_DECREF(digest);
    PyBuffer_Release(&seed_view);

    d = PyBytes_FromStringAndSize((char *)iv, 16);
    if (!d) {
        Py_DECREF(sha1);
        return NULL;
    }

    result = PyTuple_Pack(2, sha1, d);
    Py_DECREF(sha1);
    Py_DECREF(d);
    return result;

    error:
        Py_XDECREF(hashlib);
        Py_XDECREF(sha1);
        Py_XDECREF(update);
        Py_XDECREF(digest);
        PyBuffer_Release(&seed_view);
    return NULL;
}

static PyMethodDef crypto_methods[] = {
    {
        "rar3_sha1",
        rar3_sha1,
        METH_VARARGS,
        "rar3_sha1(seed) -> (sha1, iv)"
    },
  {NULL, NULL, 0, NULL},
};

static struct PyModuleDef crypto_def = {
  .m_base = PyModuleDef_HEAD_INIT,
  .m_name = "_crypto",
  .m_doc = "Native accelerations for rarfile",
  .m_size = -1,
  .m_methods = crypto_methods,
};

PyMODINIT_FUNC PyInit__crypto(void) {
    PyObject *m = PyModule_Create(&crypto_def);
    if (m == NULL) {
        return NULL;
    }
#ifdef Py_GIL_DISABLED
    PyUnstable_Module_SetGIL(m, Py_MOD_GIL_NOT_USED);
#endif
    return m;
}