"""API tests.
"""

import io
import os
from pathlib import Path

import pytest

import rarfile

#
# test start
#

def test_not_rar():
    with pytest.raises(rarfile.NotRarFile):
        rarfile.RarFile("rarfile.py", "r")
    with pytest.raises(rarfile.NotRarFile):
        with open("rarfile.py", "rb") as f:
            rarfile.RarFile(f, "r")


def test_bad_arc_mode_w():
    with pytest.raises(NotImplementedError):
        rarfile.RarFile("test/files/rar3-comment-plain.rar", "w")


def test_bad_arc_mode_rb():
    with pytest.raises(NotImplementedError):
        rarfile.RarFile("test/files/rar3-comment-plain.rar", "rb")


def test_bad_errs():
    with pytest.raises(ValueError):
        rarfile.RarFile("test/files/rar3-comment-plain.rar", "r", errors="foo")


def test_bad_open_mode_w():
    rf = rarfile.RarFile("test/files/rar3-comment-plain.rar")
    with pytest.raises(NotImplementedError):
        rf.open("qwe", "w")


def test_bad_open_psw():
    rf = rarfile.RarFile("test/files/rar3-comment-psw.rar")
    with pytest.raises(rarfile.PasswordRequired):
        rf.open("file1.txt")


def test_bad_filelike():
    with pytest.raises(ValueError):
        rarfile.is_rarfile(bytearray(10))


def test_open_psw_late_rar3():
    rf = rarfile.RarFile("test/files/rar3-comment-psw.rar")
    d1 = rf.open("file1.txt", "r", "password").read()
    d2 = rf.open("file1.txt", "r", b"password").read()
    assert d1 == d2


def test_open_psw_late_rar5():
    rf = rarfile.RarFile("test/files/rar5-psw.rar")
    rf.open("stest1.txt", "r", "password").read()
    rf.open("stest1.txt", "r", b"password").read()


def test_open_pathlib_path():
    rf = rarfile.RarFile("test/files/rar5-psw.rar")
    rf.open(Path("stest1.txt"), "r", "password").read()


def test_read_psw_late_rar3():
    rf = rarfile.RarFile("test/files/rar3-comment-psw.rar")
    rf.read("file1.txt", "password")
    rf.read("file1.txt", b"password")


def test_read_psw_late_rar5():
    rf = rarfile.RarFile("test/files/rar5-psw.rar")
    rf.read("stest1.txt", "password")
    rf.read("stest1.txt", b"password")


def test_open_psw_late():
    rf = rarfile.RarFile("test/files/rar5-psw.rar")
    with pytest.raises(rarfile.BadRarFile):
        rf.read("stest1.txt", "password222")


def test_create_from_pathlib_path():
    # Make sure we can open both relative and absolute Paths
    rarfile.RarFile(Path("test/files/rar5-psw.rar"))
    rarfile.RarFile(Path("test/files/rar5-psw.rar").resolve())


def test_detection():
    assert rarfile.is_rarfile("test/files/ctime4.rar.exp") is False
    assert rarfile.is_rarfile("test/files/ctime4.rar") is True
    assert rarfile.is_rarfile("test/files/rar5-crc.rar") is True

    assert rarfile.is_rarfile(Path("test/files/rar5-crc.rar")) is True


def test_signature_error():
    with pytest.raises(rarfile.NotRarFile):
        rarfile.RarFile("test/files/ctime4.rar.exp")


def test_signature_error_mem():
    data = io.BytesIO(b"x" * 40)
    with pytest.raises(rarfile.NotRarFile):
        rarfile.RarFile(data)


def test_with():
    with rarfile.RarFile("test/files/rar5-crc.rar") as rf:
        data = rf.read("stest1.txt")
        with rf.open("stest1.txt") as f:
            dst = io.BytesIO()
            while True:
                buf = f.read(7)
                if not buf:
                    break
                dst.write(buf)
            assert dst.getvalue() == data


def test_readline():
    def load_readline(rf, fn):
        with rf.open(fn) as f:
            tr = io.TextIOWrapper(io.BufferedReader(f))
            res = []
            while True:
                ln = tr.readline()
                if not ln:
                    break
                res.append(ln)
        return res

    rf = rarfile.RarFile("test/files/seektest.rar")
    v1 = load_readline(rf, "stest1.txt")
    v2 = load_readline(rf, "stest2.txt")
    assert len(v1) == 512
    assert v1 == v2


def test_printdir(capsys):
    rf = rarfile.RarFile("test/files/seektest.rar")
    rf.printdir()
    res = capsys.readouterr()
    assert res.out == "stest1.txt\nstest2.txt\n"


def test_testrar():
    rf = rarfile.RarFile("test/files/seektest.rar")
    rf.testrar()


def test_iter():
    rf = rarfile.RarFile("test/files/seektest.rar")
    n1 = rf.namelist()
    n2 = [m.filename for m in rf]
    assert n1 == n2


def test_testrar_mem():
    with open("test/files/seektest.rar", "rb") as f:
        arc = f.read()
    rf = rarfile.RarFile(io.BytesIO(arc))
    rf.testrar()


def test_extract(tmp_path):
    ex1 = tmp_path / "extract1"
    ex2 = tmp_path / "extract2"
    ex3 = tmp_path / "extract3"
    os.makedirs(str(ex1))
    os.makedirs(str(ex2))
    os.makedirs(str(ex3))
    rf = rarfile.RarFile("test/files/seektest.rar")

    rf.extractall(str(ex1))
    assert os.path.isfile(str(ex1 / "stest1.txt")) is True
    assert os.path.isfile(str(ex1 / "stest2.txt")) is True

    rf.extract("stest1.txt", str(ex2))
    assert os.path.isfile(str(ex2 / "stest1.txt")) is True
    assert os.path.isfile(str(ex2 / "stest2.txt")) is False

    inf = rf.getinfo("stest2.txt")
    rf.extract(inf, str(ex3))
    assert os.path.isfile(str(ex3 / "stest1.txt")) is False
    assert os.path.isfile(str(ex3 / "stest2.txt")) is True

    rf.extractall(str(ex2), ["stest1.txt"])
    assert os.path.isfile(str(ex2 / "stest1.txt")) is True

    rf.extractall(str(ex3), [rf.getinfo("stest2.txt")])
    assert os.path.isfile(str(ex3 / "stest2.txt")) is True

    ex4 = tmp_path / "extract4"
    os.makedirs(str(ex4))
    rf.extractall(ex4)
    assert os.path.isfile(str(ex4 / "stest1.txt")) is True
    assert os.path.isfile(str(ex4 / "stest2.txt")) is True


def test_extract_mem(tmp_path):
    ex1 = tmp_path / "extract11"
    ex2 = tmp_path / "extract22"
    ex3 = tmp_path / "extract33"
    os.makedirs(str(ex1))
    os.makedirs(str(ex2))
    os.makedirs(str(ex3))

    with open("test/files/seektest.rar", "rb") as f:
        arc = f.read()
    rf = rarfile.RarFile(io.BytesIO(arc))

    rf.extractall(str(ex1))
    assert os.path.isfile(str(ex1 / "stest1.txt")) is True
    assert os.path.isfile(str(ex1 / "stest2.txt")) is True

    rf.extract("stest1.txt", str(ex2))
    assert os.path.isfile(str(ex2 / "stest1.txt")) is True
    assert os.path.isfile(str(ex2 / "stest2.txt")) is False

    inf = rf.getinfo("stest2.txt")
    rf.extract(inf, str(ex3))
    assert os.path.isfile(str(ex3 / "stest1.txt")) is False
    assert os.path.isfile(str(ex3 / "stest2.txt")) is True


def get_rftype(h):
    assert h.is_dir() == h.isdir()
    return "".join([
        h.is_file() and "F" or "-",
        h.is_dir() and "D" or "-",
        h.is_symlink() and "L" or "-",
    ])


def test_infocb():
    infos = []

    def info_cb(info):
        infos.append((info.type, info.needs_password(), get_rftype(info), info._must_disable_hack()))

    rf = rarfile.RarFile("test/files/seektest.rar", info_callback=info_cb)
    assert infos == [
        (rarfile.RAR_BLOCK_MAIN, False, "---", False),
        (rarfile.RAR_BLOCK_FILE, False, "F--", False),
        (rarfile.RAR_BLOCK_FILE, False, "F--", False),
        (rarfile.RAR_BLOCK_ENDARC, False, "---", False)]
    rf.close()

    infos = []
    rf = rarfile.RarFile("test/files/rar5-solid-qo.rar", info_callback=info_cb)
    assert infos == [
        (rarfile.RAR_BLOCK_MAIN, False, "---", True),
        (rarfile.RAR_BLOCK_FILE, False, "F--", False),
        (rarfile.RAR_BLOCK_FILE, False, "F--", True),
        (rarfile.RAR_BLOCK_FILE, False, "F--", True),
        (rarfile.RAR_BLOCK_FILE, False, "F--", True),
        (rarfile.RAR_BLOCK_SUB, False, "---", False),
        (rarfile.RAR_BLOCK_ENDARC, False, "---", False)]
    rf.close()


# pylint: disable=singleton-comparison
def test_rarextfile():
    with rarfile.RarFile("test/files/seektest.rar") as rf:
        for fn in ("stest1.txt", "stest2.txt"):
            with rf.open(fn) as f:
                assert f.tell() == 0
                assert f.writable() == False
                assert f.seekable() == True
                assert f.readable() == True
                assert f.readall() == rf.read(fn)

