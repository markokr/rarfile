"""Read all test files.
"""

import io
from glob import glob

import pytest

import rarfile

ARCHIVE_COMMENTS = {
    "rar15-comment-lock.rar": "RARcomment -----",
    "rar15-comment.rar": "RARcomment -----",
    "rar202-comment-nopsw.rar": "RARcomment",
    "rar202-comment-psw.rar": "RARcomment",
    "rar3-comment-hpsw.rar": "RARcomment\n",
    "rar3-comment-plain.rar": "RARcomment\n",
    "rar3-comment-psw.rar": "RARcomment\n",
    "rar5-blake.rar": "RAR5 archive - blake\n",
    "rar5-crc.rar": "RAR5 archive - crc\n",
    "rar5-crc.sfx": "RAR5 archive - crc\n",
    "rar5-hpsw.rar": "RAR5 archive - hdr-password\n",
    "rar5-psw-blake.rar": "RAR5 archive - nohdr-password-blake\n",
    "rar5-psw.rar": "RAR5 archive - nohdr-password\n",
}

ARCHIVE_FILES = [
    f.replace("\\", "/")
    for f in sorted(glob("test/files/*.rar"))
    if "hpsw" not in f
]


def run_reading_normal(fn, comment):
    try:
        rf = rarfile.RarFile(fn)
    except rarfile.NeedFirstVolume:
        return
    if rf.needs_password():
        rf.setpassword("password")
    assert rf.strerror() is None
    assert rf.comment == comment
    for ifn in rf.namelist():
        if ifn.endswith("/"):
            continue

        info = rf.getinfo(ifn)
        if info.is_dir():
            continue
        if info.is_symlink():
            continue

        # full read
        rf.read(ifn)

        # read from stream
        item = rf.getinfo(ifn)
        f = rf.open(ifn)
        total = 0
        while True:
            buf = f.read(1024)
            if not buf:
                break
            total += len(buf)
        f.close()
        assert total == item.file_size, ifn

        # read from stream with readinto
        bbuf = bytearray(1024)
        with rf.open(ifn) as f:
            res = f.readinto(memoryview(bbuf))
            if res == 0:
                break


def run_reading_inmem(fn, comment):
    try:
        rf = rarfile.RarFile(fn)
    except rarfile.NeedFirstVolume:
        return
    if len(rf.volumelist()) > 1:
        return

    with io.open(fn, "rb") as f:
        buf = f.read()
    run_reading_normal(io.BytesIO(buf), comment)


def run_reading(fn):
    basename = fn.split("/")[-1]
    comment = ARCHIVE_COMMENTS.get(basename)
    run_reading_normal(fn, comment)
    run_reading_inmem(fn, comment)


@pytest.mark.parametrize("fn", ARCHIVE_FILES)
def test_reading(fn):
    run_reading(fn)


@pytest.mark.skipif(not rarfile._have_crypto, reason="No crypto")
def test_reading_rar3_hpsw():
    run_reading("test/files/rar3-comment-hpsw.rar")


@pytest.mark.skipif(rarfile._have_crypto, reason="Has crypto")
def test_reading_rar3_hpsw_nocrypto():
    with pytest.raises(rarfile.NoCrypto):
        run_reading("test/files/rar3-comment-hpsw.rar")


@pytest.mark.skipif(not rarfile._have_crypto, reason="No crypto")
def test_reading_rar5_hpsw():
    run_reading("test/files/rar5-hpsw.rar")


@pytest.mark.skipif(rarfile._have_crypto, reason="Has crypto")
def test_reading_rar5_hpsw_nocrypto():
    with pytest.raises(rarfile.NoCrypto):
        run_reading("test/files/rar5-hpsw.rar")


def test_reading_rar3_sfx():
    assert rarfile.is_rarfile("test/files/rar3-seektest.sfx") is False
    assert rarfile.is_rarfile_sfx("test/files/rar3-seektest.sfx") is True
    run_reading("test/files/rar3-seektest.sfx")
    run_reading("test/files/rar3-seektest.sfx")


def test_reading_rar5_crc_sfx():
    assert rarfile.is_rarfile("test/files/rar5-crc.sfx") is False
    assert rarfile.is_rarfile_sfx("test/files/rar5-crc.sfx") is True
    run_reading("test/files/rar5-crc.sfx")

