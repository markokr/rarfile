# rarfile.crypto
#
# Copyright (c) 2005-2026  Marko Kreen <markokr@gmail.com>
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

"""Pure-python fallback for the rarfile._crypto C extension.

Used when the C extension could not be built or imported.
"""

from hashlib import sha1
from struct import pack_into, unpack_from

__all__ = ["rar3_sha1"]


def _rar3_corrupt_block(seed, pos):
    """Emulate one block of the buggy RAR3 SHA1 corruption.

    Reads a 64-byte block as 16 big-endian words, runs the SHA1 message
    schedule expansion (rounds 16..79) over a rolling 16-word window, then
    writes the resulting words back little-endian, mutating the block in place.
    """
    w = list(unpack_from(">16L", seed, pos))
    for i in range(16, 80):
        x = w[(i - 3) & 15] ^ w[(i - 8) & 15] ^ w[(i - 14) & 15] ^ w[(i - 16) & 15]
        w[i & 15] = ((x << 1) | (x >> 31)) & 0xFFFFFFFF
    pack_into("<16L", seed, pos, *w)


def rar3_sha1(seed):
    """Run the full RAR3 string-to-key hash (16 outer loops of 0x4000 iterations).

    Each iteration feeds ``seed`` and a 3-byte little-endian counter into the
    SHA1 update, then corrupts ``seed`` in place for every full 64-byte block
    (the RAR3 bug).

    Returns a ``(sha1, iv)`` tuple: the hashlib.sha1() object holding the
    final key state, and the 16-byte IV.
    """
    seed_len = len(seed)
    iv = bytearray(16)
    nbytes = 0

    h = sha1()
    update = h.update
    digest = h.digest

    for i in range(16):
        base = i << 14
        for j in range(0x4000):
            update(seed)

            # Corrupt each full 64-byte block
            bufpos = nbytes & 63
            nbytes += seed_len
            if seed_len > 64:
                dpos = 64 - bufpos
                while dpos + 64 <= seed_len:
                    _rar3_corrupt_block(seed, dpos)
                    dpos += 64

            x = base + j
            update(bytes((x & 0xFF, (x >> 8) & 0xFF, (x >> 16) & 0xFF)))
            # counter is only 3 bytes, so it never triggers the corruption
            nbytes += 3

            if j == 0:
                iv[i] = digest()[19]

    return h, bytes(iv)
