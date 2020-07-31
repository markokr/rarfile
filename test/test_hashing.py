"""Hashing tests.
"""

import hashlib
from binascii import hexlify, unhexlify

import rarfile
from rarfile import Blake2SP, CRC32Context, NoHashContext, Rar3Sha1


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


def test_rar3_sha1():
    for n in range(0, 200):
        data = bytearray(range(n))
        h1 = hashlib.sha1(data).hexdigest()
        h2 = Rar3Sha1(data).hexdigest()
        assert h1 == h2

    data = bytearray([(i & 255) for i in range(2000)])
    x1 = hashlib.sha1()
    x2 = Rar3Sha1()
    for step in (3, 17, 67, 128, 157):
        pos = 0
        while pos < len(data):
            pos2 = pos + step
            if pos2 > len(data):
                pos2 = len(data)
            x1.update(data[pos:pos2])
            x2.update(data[pos:pos2])
            assert x1.hexdigest() == x2.hexdigest()
            pos = pos2


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

