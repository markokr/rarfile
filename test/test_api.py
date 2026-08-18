"""API tests.
"""

# pylint: disable=use-implicit-booleaness-not-comparison

import io
import os
from pathlib import Path

import pytest

import rarfile
from rarfile.bits import (
    RAR_BLOCK_ENDARC, RAR_BLOCK_FILE, RAR_BLOCK_MAIN, RAR_BLOCK_SUB,
)

#
# test start
#


def test_not_rar() -> None:
    with pytest.raises(rarfile.NotRarFile):
        rarfile.RarFile(__file__, "r")
    with pytest.raises(rarfile.NotRarFile):
        with open(__file__, "rb") as f:
            rarfile.RarFile(f, "r")


def test_bad_arc_mode_w() -> None:
    with pytest.raises(NotImplementedError):
        rarfile.RarFile("test/files/rar3-comment-plain.rar", "w")


def test_bad_arc_mode_rb() -> None:
    with pytest.raises(NotImplementedError):
        rarfile.RarFile("test/files/rar3-comment-plain.rar", "rb")


def test_bad_errs() -> None:
    with pytest.raises(ValueError):
        rarfile.RarFile("test/files/rar3-comment-plain.rar", "r", errors="foo")  # type: ignore[arg-type]


def test_errors_param() -> None:
    with open("test/files/rar3-comment-plain.rar", "rb") as f:
        data = f.read()
    buf = io.BytesIO(data[:17])
    with rarfile.RarFile(buf, "r", errors="stop") as rf:
        assert rf.namelist() == []
    with pytest.raises(rarfile.BadRarFile):
        rarfile.RarFile(buf, "r", errors="strict")


def test_bad_open_mode_w() -> None:
    rf = rarfile.RarFile("test/files/rar3-comment-plain.rar")
    with pytest.raises(NotImplementedError):
        rf.open("qwe", "w")


def test_bad_open_psw() -> None:
    rf = rarfile.RarFile("test/files/rar3-comment-psw.rar")
    with pytest.raises(rarfile.PasswordRequired):
        rf.open("file1.txt")


def test_bad_filelike() -> None:
    with pytest.raises(ValueError):
        rarfile.is_rarfile(bytearray(10))  # type: ignore[arg-type]


def test_open_psw_late_rar3() -> None:
    rf = rarfile.RarFile("test/files/rar3-comment-psw.rar")
    d1 = rf.open("file1.txt", "r", "password").read()
    d2 = rf.open("file1.txt", "r", b"password").read()  # type: ignore[arg-type]
    assert d1 == d2


def test_open_psw_late_rar5() -> None:
    rf = rarfile.RarFile("test/files/rar5-psw.rar")
    rf.open("stest1.txt", "r", "password").read()
    rf.open("stest1.txt", "r", b"password").read()  # type: ignore[arg-type]


def test_open_pathlib_path() -> None:
    rf = rarfile.RarFile("test/files/rar5-psw.rar")
    rf.open(Path("stest1.txt"), "r", "password").read()


def test_read_psw_late_rar3() -> None:
    rf = rarfile.RarFile("test/files/rar3-comment-psw.rar")
    rf.read("file1.txt", "password")
    rf.read("file1.txt", b"password")  # type: ignore[arg-type]


def test_read_psw_late_rar5() -> None:
    rf = rarfile.RarFile("test/files/rar5-psw.rar")
    rf.read("stest1.txt", "password")
    rf.read("stest1.txt", b"password")  # type: ignore[arg-type]


def test_open_psw_late() -> None:
    rf = rarfile.RarFile("test/files/rar5-psw.rar")
    with pytest.raises(rarfile.BadRarFile):
        rf.read("stest1.txt", "password222")


def test_create_from_pathlib_path() -> None:
    # Make sure we can open both relative and absolute Paths
    rarfile.RarFile(Path("test/files/rar5-psw.rar"))
    rarfile.RarFile(Path("test/files/rar5-psw.rar").resolve())


def test_detection() -> None:
    assert rarfile.is_rarfile("test/files/ctime4.rar.exp") is False
    assert rarfile.is_rarfile("test/files/ctime4.rar") is True
    assert rarfile.is_rarfile("test/files/rar5-crc.rar") is True

    assert rarfile.is_rarfile(Path("test/files/rar5-crc.rar")) is True

    assert rarfile.is_rarfile("test/files/_missing_.rar") is False


def test_restore_pos() -> None:
    with open('test/files/rar5-crc.rar', 'rb') as fd:
        fd.seek(3)
        assert rarfile.is_rarfile(fd) is True
        assert fd.tell() == 3


def test_getinfo() -> None:
    with rarfile.RarFile("test/files/rar5-crc.rar") as rf:
        inf = rf.getinfo("stest1.txt")
        assert isinstance(inf, rarfile.RarInfo)
        assert rf.getinfo(inf) is inf
        with pytest.raises(rarfile.NoRarEntry):
            rf.getinfo("missing.txt")


def test_signature_error() -> None:
    with pytest.raises(rarfile.NotRarFile):
        rarfile.RarFile("test/files/ctime4.rar.exp")


def test_signature_error_mem() -> None:
    data = io.BytesIO(b"x" * 40)
    with pytest.raises(rarfile.NotRarFile):
        rarfile.RarFile(data)


def test_with() -> None:
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


def test_readline() -> None:
    def load_readline(rf: rarfile.RarFile, fn: str) -> list[str]:
        with rf.open(fn) as f:
            assert isinstance(f, rarfile.RarExtFile)
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


def run_parallel(rfile: str | rarfile.FileLike, entry: str) -> None:
    buf1, buf2 = [], []
    rf = rarfile.RarFile(rfile)
    count = 0
    with rf.open(entry) as f1:
        with rf.open(entry) as f2:
            for _ in range(10000):
                res1 = f1.read(10)
                res2 = f2.read(10)
                if res1:
                    buf1.append(res1)
                    count += len(res1)
                if res2:
                    buf2.append(res2)
                    count += len(res2)
                if not res1 and not res2:
                    break

    assert buf1
    assert buf1 == buf2


def test_parallel_file_compressed() -> None:
    run_parallel("test/files/seektest.rar", "stest1.txt")


def test_parallel_file_direct() -> None:
    run_parallel("test/files/seektest.rar", "stest2.txt")


def test_parallel_fd_compressed() -> None:
    with open("test/files/seektest.rar", "rb") as f:
        memfile = io.BytesIO(f.read())
    run_parallel(memfile, "stest1.txt")


def test_parallel_fd_direct() -> None:
    with open("test/files/seektest.rar", "rb") as f:
        memfile = io.BytesIO(f.read())
    run_parallel(memfile, "stest2.txt")


def test_printdir(capsys: pytest.CaptureFixture[str]) -> None:
    rf = rarfile.RarFile("test/files/seektest.rar")
    rf.printdir()
    res = capsys.readouterr()
    assert res.out == "stest1.txt\nstest2.txt\n"


def test_testrar() -> None:
    rf = rarfile.RarFile("test/files/seektest.rar")
    rf.testrar()


def test_iter() -> None:
    rf = rarfile.RarFile("test/files/seektest.rar")
    n1 = rf.namelist()
    n2 = [m.filename for m in rf]
    assert n1 == n2


def test_testrar_mem() -> None:
    with open("test/files/seektest.rar", "rb") as f:
        arc = f.read()
    rf = rarfile.RarFile(io.BytesIO(arc))
    rf.testrar()


def test_extract(tmp_path: Path) -> None:
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


def test_extract_mem(tmp_path: Path) -> None:
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


def get_rftype(h: rarfile.RarEntry) -> str:
    if not isinstance(h, rarfile.RarInfo):
        return "---"
    assert h.is_dir() == h.isdir()
    return "".join([
        h.is_file() and "F" or "-",
        h.is_dir() and "D" or "-",
        h.is_symlink() and "L" or "-",
    ])


def test_infocb() -> None:
    infos = []

    def info_cb(info: rarfile.RarEntry) -> None:
        infos.append((info.type, info.needs_password(), get_rftype(info), info._must_disable_hack()))

    rf = rarfile.RarFile("test/files/seektest.rar", info_callback=info_cb)
    assert infos == [
        (RAR_BLOCK_MAIN, False, "---", False),
        (RAR_BLOCK_FILE, False, "F--", False),
        (RAR_BLOCK_FILE, False, "F--", False),
        (RAR_BLOCK_ENDARC, False, "---", False)]
    rf.close()

    infos = []
    rf = rarfile.RarFile("test/files/rar5-solid-qo.rar", info_callback=info_cb)
    assert infos == [
        (RAR_BLOCK_MAIN, False, "---", True),
        (RAR_BLOCK_FILE, False, "F--", False),
        (RAR_BLOCK_FILE, False, "F--", True),
        (RAR_BLOCK_FILE, False, "F--", True),
        (RAR_BLOCK_FILE, False, "F--", True),
        (RAR_BLOCK_SUB, False, "---", False),
        (RAR_BLOCK_ENDARC, False, "---", False)]
    rf.close()


# pylint: disable=singleton-comparison
def test_rarextfile() -> None:
    with rarfile.RarFile("test/files/seektest.rar") as rf:
        for fn in ("stest1.txt", "stest2.txt"):
            with rf.open(fn) as f:
                assert isinstance(f, rarfile.RarExtFile)
                assert f.tell() == 0
                assert f.writable() == False
                assert f.seekable() == True
                assert f.readable() == True
                assert f.readall() == rf.read(fn)


def test_is_rarfile() -> None:
    with rarfile.RarFile("test/files/seektest.rar") as rf:
        for fn in ("stest1.txt", "stest2.txt"):
            with rf.open(fn) as f:
                assert isinstance(f, rarfile.RarExtFile)
                assert f.tell() == 0
                assert f.writable() == False
                assert f.seekable() == True
                assert f.readable() == True
                assert f.readall() == rf.read(fn)


def test_part_only() -> None:
    info_list = []

    def info_cb(info: rarfile.RarEntry) -> None:
        info_list.append(info)

    with pytest.raises(rarfile.NeedFirstVolume):
        with rarfile.RarFile("test/files/rar3-vols.part2.rar") as rf:
            pass
    with rarfile.RarFile("test/files/rar3-vols.part2.rar", part_only=True, info_callback=info_cb) as rf:
        assert len(info_list) == 3

    with pytest.raises(rarfile.NeedFirstVolume):
        with rarfile.RarFile("test/files/rar5-vols.part2.rar") as rf:
            pass
    info_list = []
    with rarfile.RarFile("test/files/rar5-vols.part2.rar", part_only=True, info_callback=info_cb) as rf:
        assert len(info_list) == 5


def test_volume_info() -> None:
    info_list = []

    def info_cb(info: rarfile.RarEntry) -> None:
        info_list.append(info)
    with rarfile.RarFile("test/files/rar3-vols.part1.rar", info_callback=info_cb) as rf:
        assert len(info_list) == 10
    info_list = []
    with rarfile.RarFile("test/files/rar5-vols.part1.rar", info_callback=info_cb) as rf:
        assert len(info_list) == 16


def test_is_solid() -> None:
    with rarfile.RarFile("test/files/rar3-comment-plain.rar") as rf:
        assert not rf.is_solid()
    with rarfile.RarFile("test/files/rar3-solid.rar") as rf:
        assert rf.is_solid()
    with rarfile.RarFile("test/files/rar5-crc.rar") as rf:
        assert not rf.is_solid()
    with rarfile.RarFile("test/files/rar5-solid.rar") as rf:
        assert rf.is_solid()


def test_public_exports() -> None:
    missing = object()
    for k in rarfile.__all__:
        assert getattr(rarfile, k, missing) is not missing, f"rarfile.{k} is missing"
