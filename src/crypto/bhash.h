/*
 * Buffered hash.
 */

#ifndef CRYPTO_BHASH_H
#define CRYPTO_BHASH_H

#include <stdbool.h>

#define BHASH_BUFSIZE (1024)
#define BHASH_NULL { .update = NULL, .digest = NULL }

struct BufferedHash {
	PyObject *update;
	PyObject *digest;
	size_t pos;
	size_t nbytes;
	uint8_t data[BHASH_BUFSIZE];
};

bool bhash_init(struct BufferedHash *buf, const char *algo);
bool bhash_flush(struct BufferedHash *buf);
bool bhash_update(struct BufferedHash *buf, const uint8_t *data, size_t size);
PyObject *bhash_digest(struct BufferedHash *buf);
void bhash_free(struct BufferedHash *buf);

#endif
