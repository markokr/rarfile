"""Test seeking on files.
"""

import io

import pytest

import rarfile

ARC = "test/files/seektest.rar"

_WHENCE = 0


def do_seek(f, pos, lim, size=None):
    global _WHENCE
    ofs = pos * 4
    fsize = lim * 4

    if ofs < 0:
        exp = 0
    elif ofs > fsize:
        exp = fsize
    else:
        exp = ofs

    if size:
        cur = f.tell()
        if _WHENCE == 0:
            f.seek(ofs, _WHENCE)
        elif _WHENCE == 1:
            f.seek(ofs - cur, _WHENCE)
        else:
            assert _WHENCE == 2
            f.seek(ofs - size, _WHENCE)
        _WHENCE = (_WHENCE + 1) % 3
    else:
        f.seek(ofs)

    got = f.tell()

    assert got == exp
    ln = f.read(4)
    if got == fsize and ln:
        raise Exception("unexpected read")
    if not ln and got < fsize:
        raise Exception("unexpected read failure")
    if ln:
        spos = int(ln)
        assert spos * 4 == got


def run_seek(rf, fn):
    inf = rf.getinfo(fn)
    cnt = int(inf.file_size / 4)
    f = rf.open(fn)

    with pytest.raises(ValueError):
        f.seek(0, -1)
    with pytest.raises(ValueError):
        f.seek(0, 3)

    do_seek(f, int(cnt / 2), cnt)
    do_seek(f, 0, cnt)

    for i in range(int(cnt / 2)):
        do_seek(f, i * 2, cnt, inf.file_size)

    for i in range(cnt):
        do_seek(f, i * 2 - int(cnt / 2), cnt, inf.file_size)

    for i in range(cnt + 10):
        do_seek(f, cnt - i - 5, cnt, inf.file_size)

    f.close()


def run_arc(arc, desc):
    files = ["stest1.txt", "stest2.txt"]
    rf = rarfile.RarFile(arc)
    for fn in files:
        run_seek(rf, fn)


def test_seek_filename():
    run_arc(ARC, "fn")


def test_seek_bytesio():
    # filelike: io.BytesIO, io.open()
    with open(ARC, "rb") as f:
        data = f.read()
    run_arc(io.BytesIO(data), "io.BytesIO")


def test_seek_open():
    # filelike: file()
    with open(ARC, "rb") as f:
        run_arc(f, "open")


def test_seek_ioopen():
    # filelike: io.open()
    with io.open(ARC, "rb") as f:
        run_arc(f, "io.open")

