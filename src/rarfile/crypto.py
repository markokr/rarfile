"""Low-level crypto helpers.
"""

from binascii import crc32, hexlify
from hashlib import blake2s, pbkdf2_hmac, sha1
from struct import Struct

from .bits import RAR_MAX_PASSWORD
from .errors import BadRarFile

__all__ = ("rar3_s2k", "rar5_s2k", "BadRarFile", "NoHashContext", "CRC32Context", "Blake2SP", "HeaderDecrypt")


BLK_BE = Struct(">16L")
BLK_LE = Struct("<16L")

KEY_BE = Struct(">4L")
KEY_LE = Struct("<4L")

U16_LE = Struct('<H')

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


class HeaderDecrypt:
    """File-like object that decrypts from another file"""

    def __init__(self, f, key, iv):
        self.f = f
        self.ciph = AES_CBC_Decrypt(key, iv)
        self.buf = b""

    def tell(self):
        """Current file pos - works only on block boundaries."""
        return self.f.tell()

    def read(self, cnt=None):
        """Read and decrypt."""
        if cnt > 8 * 1024:
            raise BadRarFile("Bad count to header decrypt - wrong password?")

        # consume old data
        if cnt <= len(self.buf):
            res = self.buf[:cnt]
            self.buf = self.buf[cnt:]
            return res
        res = self.buf
        self.buf = b""
        cnt -= len(res)

        # decrypt new data
        blklen = 16
        while cnt > 0:
            enc = self.f.read(blklen)
            if len(enc) < blklen:
                break
            dec = self.ciph.decrypt(enc)
            if cnt >= len(dec):
                res += dec
                cnt -= len(dec)
            else:
                res += dec[:cnt]
                self.buf = dec[cnt:]
                cnt = 0

        return res


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
    __slots__ = ("_crc",)

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
    __slots__ = ("_thread", "_buf", "_cur", "_digest")
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


def generate():
    import textwrap
    words = [chr(ord('a') + i) for i in range(16)]
    all_words = ", ".join(words)
    header = f"""\
        def rar3_corrupt_block(seed, pos):
            {all_words} = BLK_BE.unpack_from(seed, pos)
            for _ in range(4):
    """.rstrip()
    footer = f"    BLK_LE.pack_into(seed, pos, {all_words})"
    lines = [textwrap.dedent(header)]
    for i in range(16):
        a = words[(i - 3) & 15]
        b = words[(i - 8) & 15]
        c = words[(i - 14) & 15]
        d = words[(i - 16) & 15]
        step1 = f"x = {a} ^ {b} ^ {c} ^ {d}"
        step2 = f"{d} = ((x << 1) | (x >> 31)) & 0xFFFFFFFF"
        lines.append(f"        {step1}; {step2}")
    lines.append(footer)
    print("\n".join(lines))


def rar3_corrupt_block(seed, pos):
    a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p = BLK_BE.unpack_from(seed, pos)
    for _ in range(4):
        # fmt: off
        x = n ^ i ^ c ^ a; a = ((x << 1) | (x >> 31)) & 0xFFFFFFFF
        x = o ^ j ^ d ^ b; b = ((x << 1) | (x >> 31)) & 0xFFFFFFFF
        x = p ^ k ^ e ^ c; c = ((x << 1) | (x >> 31)) & 0xFFFFFFFF
        x = a ^ l ^ f ^ d; d = ((x << 1) | (x >> 31)) & 0xFFFFFFFF
        x = b ^ m ^ g ^ e; e = ((x << 1) | (x >> 31)) & 0xFFFFFFFF
        x = c ^ n ^ h ^ f; f = ((x << 1) | (x >> 31)) & 0xFFFFFFFF
        x = d ^ o ^ i ^ g; g = ((x << 1) | (x >> 31)) & 0xFFFFFFFF
        x = e ^ p ^ j ^ h; h = ((x << 1) | (x >> 31)) & 0xFFFFFFFF
        x = f ^ a ^ k ^ i; i = ((x << 1) | (x >> 31)) & 0xFFFFFFFF
        x = g ^ b ^ l ^ j; j = ((x << 1) | (x >> 31)) & 0xFFFFFFFF
        x = h ^ c ^ m ^ k; k = ((x << 1) | (x >> 31)) & 0xFFFFFFFF
        x = i ^ d ^ n ^ l; l = ((x << 1) | (x >> 31)) & 0xFFFFFFFF
        x = j ^ e ^ o ^ m; m = ((x << 1) | (x >> 31)) & 0xFFFFFFFF
        x = k ^ f ^ p ^ n; n = ((x << 1) | (x >> 31)) & 0xFFFFFFFF
        x = l ^ g ^ a ^ o; o = ((x << 1) | (x >> 31)) & 0xFFFFFFFF
        x = m ^ h ^ b ^ p; p = ((x << 1) | (x >> 31)) & 0xFFFFFFFF
        # fmt: on
    BLK_LE.pack_into(seed, pos, a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p)


def rar3_s2k_core_py(seed):
    """Main loop of the RAR3 string-to-key hash.
    """
    seed_len = len(seed)
    seed_buf = bytearray(seed_len + 3)
    seed_buf[:seed_len] = seed

    iv = bytearray(16)
    nbytes = 0

    h = sha1()
    update = h.update
    digest = h.digest
    set_counter = U16_LE.pack_into

    counter = 0
    for i in range(16):
        seed_buf[-1] = (counter >> 16) & 0xFF
        for j in range(0x4000):
            bufpos = nbytes & 63
            nbytes += seed_len + 3

            set_counter(seed_buf, seed_len, counter & 0xFFFF)
            counter += 1

            update(seed_buf)

            if seed_len > 64:
                dpos = 64 - bufpos
                while dpos + 64 <= seed_len:
                    rar3_corrupt_block(seed_buf, dpos)
                    dpos += 64

            if j == 0:
                iv[i] = digest()[19]

    a, b, c, d = KEY_BE.unpack_from(h.digest(), 0)
    return KEY_LE.pack(a, b, c, d), bytes(iv)


# load C version
try:
    from ._crypto import rar3_s2k_core
except ImportError:
    rar3_s2k_core = rar3_s2k_core_py


def rar3_s2k(pwd, salt, _core=rar3_s2k_core):
    """String-to-key hash for RAR3.
    """
    if not isinstance(pwd, str):
        pwd = pwd.decode("utf8")
    wstr = pwd.encode("utf-16le")[:RAR_MAX_PASSWORD * 2]
    return _core(wstr + salt)


def rar5_s2k(pwd, salt, kdf_count):
    """String-to-key hash for RAR5.
    """
    if not isinstance(pwd, str):
        pwd = pwd.decode("utf8")
    wstr = pwd.encode("utf-16le")[:RAR_MAX_PASSWORD * 2]
    ustr = wstr.decode("utf-16le").encode("utf8")
    return pbkdf2_hmac("sha256", ustr, salt, kdf_count)


if __name__ == "__main__":
    generate()
