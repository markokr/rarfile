"""Hashing tests.
"""

from binascii import hexlify, unhexlify

import pytest

import rarfile
from rarfile import Blake2SP, CRC32Context, NoHashContext


def tohex(data):
    """Return hex string."""
    return hexlify(data).decode("ascii")


def test_nohash():
    assert NoHashContext("").hexdigest() is None
    assert NoHashContext("asd").hexdigest() is None
    md = NoHashContext()
    md.update("asd")
    assert md.digest() is None


def test_crc32():
    assert CRC32Context(b"").hexdigest() == "00000000"
    assert CRC32Context(b"Hello").hexdigest() == "f7d18982"
    assert CRC32Context(b"Bye").hexdigest() == "4f7ad7d4"

    md = CRC32Context()
    md.update(b"He")
    md.update(b"ll")
    md.update(b"o")
    assert md.hexdigest() == "f7d18982"


def xblake2sp(xdata):
    data = unhexlify(xdata)
    md = Blake2SP()
    md.update(data)
    return md.hexdigest()


def xblake2sp_slow(xdata):
    data = unhexlify(xdata)
    md = Blake2SP()
    buf = memoryview(data)
    pos = 0
    while pos < len(buf):
        md.update(buf[pos: pos + 3])
        pos += 3
    return md.hexdigest()


def test_blake2sp():
    assert Blake2SP(b"").hexdigest() == "dd0e891776933f43c7d032b08a917e25741f8aa9a12c12e1cac8801500f2ca4f"
    assert Blake2SP(b"Hello").hexdigest() == "0d6bae0db99f99183d060f7994bb94b45c6490b2a0a628b8b1346ebea8ec1d66"

    assert xblake2sp("") == "dd0e891776933f43c7d032b08a917e25741f8aa9a12c12e1cac8801500f2ca4f"
    assert xblake2sp("00") == "a6b9eecc25227ad788c99d3f236debc8da408849e9a5178978727a81457f7239"

    long1 = "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f202122232425262728292a2b2c2d2e2f3031"
    assert xblake2sp(long1) == "270affa6426f1a515c9b76dfc27d181fc2fd57d082a3ba2c1eef071533a6dfb7"

    long2 = long1 * 20
    assert xblake2sp(long2) == "24a78d92592d0761a3681f32935225ca55ffb8eb16b55ab9481c89c59a985ff3"
    assert xblake2sp_slow(long2) == "24a78d92592d0761a3681f32935225ca55ffb8eb16b55ab9481c89c59a985ff3"


def test_rar3_s2k():
    exp = ("a160cb31cb262e9231c0b6fc984fbb0d", "aa54a659fb0c359b30f353a6343fb11d")
    key, iv = rarfile.rar3_s2k(b"password", unhexlify("00FF00"))
    assert (tohex(key), tohex(iv)) == exp
    key, iv = rarfile.rar3_s2k("password", unhexlify("00FF00"))
    assert (tohex(key), tohex(iv)) == exp

    exp = ("ffff33ffaf31987c899ccc2f965a8927", "bdff6873721b247afa4f978448a5aeef")
    key, iv = rarfile.rar3_s2k("p" * 28, unhexlify("1122334455667788"))
    assert (tohex(key), tohex(iv)) == exp
    exp = ("306cafde28f1ea78c9427c3ec642c0db", "173ecdf574c0bfe9e7c23bdfd96fa435")
    key, iv = rarfile.rar3_s2k("p" * 29, unhexlify("1122334455667788"))
    assert (tohex(key), tohex(iv)) == exp

    exp = ("b1bc223609af7d4f3b70e5a254ac2501", "302c97945530d7ffa7c551eb2dd21a90")
    key, iv = rarfile.rar3_s2k("p" * 127, unhexlify("1122334455667788"))
    assert (tohex(key), tohex(iv)) == exp


def test_rar3_s2k_pure_python(monkeypatch):
    """Exercise the pure-Python rar3_sha1 fallback through rar3_s2k.

    The active implementation is the C extension where it is built, so force
    the pure-Python one to keep the fallback covered everywhere. The 29-char
    case (66-byte seed) triggers the corruption path; the expensive 127-char
    multi-block case is covered by test_rar3_s2k on pure-only machines and by
    test_rar3_sha1_native_matches_pure where the extension is built.
    """
    from rarfile.crypto import rar3_sha1 as pure_rar3_sha1
    monkeypatch.setattr(rarfile, "rar3_sha1", pure_rar3_sha1)

    exp = ("a160cb31cb262e9231c0b6fc984fbb0d", "aa54a659fb0c359b30f353a6343fb11d")
    key, iv = rarfile.rar3_s2k(b"password", unhexlify("00FF00"))
    assert (tohex(key), tohex(iv)) == exp

    exp = ("306cafde28f1ea78c9427c3ec642c0db", "173ecdf574c0bfe9e7c23bdfd96fa435")
    key, iv = rarfile.rar3_s2k("p" * 29, unhexlify("1122334455667788"))
    assert (tohex(key), tohex(iv)) == exp


def test_rar3_sha1_native_matches_pure():
    """The C extension, when built, must match the pure-Python fallback exactly.

    Only runs where the extension is present (otherwise the two names are the
    same object and there is nothing to compare). The 130-byte seed forces the
    multi-block branch of the corruption loop.
    """
    from rarfile.crypto import rar3_sha1 as pure_rar3_sha1
    active_rar3_sha1 = rarfile.rar3_sha1
    if active_rar3_sha1 is pure_rar3_sha1:
        pytest.skip("C extension not built; active impl is the pure-Python one")

    seeds = (
        b"p" * 8,     # short, no corruption
        b"p" * 66,    # >64 bytes, single-block corruption
        b"p" * 130,   # multi-block corruption
    )
    for seed in seeds:
        a, b = bytearray(seed), bytearray(seed)
        h_native, iv_native = active_rar3_sha1(a)
        h_pure, iv_pure = pure_rar3_sha1(b)
        assert h_native.digest() == h_pure.digest()
        assert iv_native == iv_pure
        assert a == b

