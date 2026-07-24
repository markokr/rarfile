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

"""Low-level crypto helpers.
"""

from binascii import crc32, hexlify
from hashlib import blake2s, sha1
from struct import pack_into, unpack_from

__all__ = ("rar3_s2k_core", "AES_CBC_Decrypt", "have_crypto", "NoHashContext", "CRC32Context", "Blake2SP")


# optional: only needed for encrypted headers
AES = None
try:
    try:
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.ciphers import (
            Cipher, algorithms, modes,
        )
        have_crypto = 1
    except ImportError:
        from Crypto.Cipher import AES
        have_crypto = 2
except ImportError:
    have_crypto = 0


class AES_CBC_Decrypt:
    """Decrypt API"""
    def __init__(self, key, iv):
        if have_crypto == 2:
            self.decrypt = AES.new(key, AES.MODE_CBC, iv).decrypt
        else:
            ciph = Cipher(algorithms.AES(key), modes.CBC(iv), default_backend())
            self.decrypt = ciph.decryptor().update


class NoHashContext:
    """No-op hash function."""
    def __init__(self, data=None):
        """Initialize"""
    def update(self, data):
        """Update data"""
    def digest(self):
        """Final hash"""
    def hexdigest(self):
        """Hexadecimal digest."""


class CRC32Context:
    """Hash context that uses CRC32."""
    __slots__ = ["_crc"]

    def __init__(self, data=None):
        self._crc = 0
        if data:
            self.update(data)

    def update(self, data):
        """Process data."""
        self._crc = crc32(data, self._crc)

    def digest(self):
        """Final hash."""
        return self._crc

    def hexdigest(self):
        """Hexadecimal digest."""
        return "%08x" % self.digest()


class Blake2SP:
    """Blake2sp hash context.
    """
    __slots__ = ["_thread", "_buf", "_cur", "_digest"]
    digest_size = 32
    block_size = 64
    parallelism = 8

    def __init__(self, data=None):
        self._buf = b""
        self._cur = 0
        self._digest = None
        self._thread = []

        for i in range(self.parallelism):
            ctx = self._blake2s(i, 0, i == (self.parallelism - 1))
            self._thread.append(ctx)

        if data:
            self.update(data)

    def _blake2s(self, ofs, depth, is_last):
        return blake2s(node_offset=ofs, node_depth=depth, last_node=is_last,
                       depth=2, inner_size=32, fanout=self.parallelism)

    def _add_block(self, blk):
        self._thread[self._cur].update(blk)
        self._cur = (self._cur + 1) % self.parallelism

    def update(self, data):
        """Hash data.
        """
        view = memoryview(data)
        bs = self.block_size
        if self._buf:
            need = bs - len(self._buf)
            if len(view) < need:
                self._buf += view.tobytes()
                return
            self._add_block(self._buf + view[:need].tobytes())
            view = view[need:]
        while len(view) >= bs:
            self._add_block(view[:bs])
            view = view[bs:]
        self._buf = view.tobytes()

    def digest(self):
        """Return final digest value.
        """
        if self._digest is None:
            if self._buf:
                self._add_block(self._buf)
                self._buf = b""
            ctx = self._blake2s(0, 1, True)
            for t in self._thread:
                ctx.update(t.digest())
            self._digest = ctx.digest()
        return self._digest

    def hexdigest(self):
        """Hexadecimal digest."""
        return hexlify(self.digest()).decode("ascii")


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


def rar3_s2k_core(seed):
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
            nbytes += seed_len + 3
            if seed_len > 64:
                dpos = 64 - bufpos
                while dpos + 64 <= seed_len:
                    _rar3_corrupt_block(seed, dpos)
                    dpos += 64

            x = base + j
            update(bytes((x & 0xFF, (x >> 8) & 0xFF, (x >> 16) & 0xFF)))

            if j == 0:
                iv[i] = digest()[19]

    return h, bytes(iv)
