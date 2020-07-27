"""Extract tests.
"""

import os
import sys
from datetime import datetime

import pytest

import rarfile

def san_unix(fn):
    return rarfile.sanitize_filename(fn, "/", False)


def san_win32(fn):
    return rarfile.sanitize_filename(fn, "/", True)


def test_sanitize_unix():
    assert san_unix("asd/asd") == "asd/asd"
    assert san_unix("asd/../asd") == "asd/asd"
    assert san_unix("c:/a/x") == r"c:/a/x"
    assert san_unix("z/./../a /b./c") == "z/a /b./c"
    assert san_unix("z<>*?:") == "z____:"


def test_sanitize_win32():
    assert san_win32("asd/asd") == "asd/asd"
    assert san_win32("asd/../asd") == "asd/asd"
    assert san_win32("c:/a/x") == "a/x"
    assert san_win32("z/./../a /b./c") == "z/a_/b_/c"
    assert san_win32("z<>*?:\\^") == "z_______"


def checktime(fn, exp_mtime):
    # cannot check subsecond precision as filesystem may not support it
    cut = len("0000-00-00 00:00:00")
    st = os.stat(fn)
    got_mtime = datetime.fromtimestamp(st.st_mtime, exp_mtime.tzinfo)
    exp_stamp = exp_mtime.isoformat(" ", "seconds")[:cut]
    got_stamp = got_mtime.isoformat(" ", "seconds")[:cut]
    assert exp_stamp == got_stamp


def checkfile(fn, data, mtime):
    with open(fn, "r") as f:
        got = f.read()
        assert got.strip() == data

    checktime(fn, mtime)


def check_subdir(rf, tmp_path):
    # pre-mkdir
    ext1 = tmp_path / "ext1"
    inf = rf.getinfo("sub/dir1/file1.txt")
    os.mkdir(ext1)
    rf.extract(inf, ext1)
    assert sorted(os.listdir(tmp_path)) == ["ext1"]
    assert os.listdir(ext1 / "sub") == ["dir1"]
    checkfile(ext1 / "sub/dir1/file1.txt", "file1", inf.mtime)

    # no mkdir
    ext2 = tmp_path / "ext2"
    inf = rf.getinfo("sub/dir2/file2.txt")
    rf.extract("sub/dir2/file2.txt", ext2)
    assert sorted(os.listdir(tmp_path)) == ["ext1", "ext2"]
    assert os.listdir(ext2 / "sub") == ["dir2"]
    checkfile(ext2 / "sub/dir2/file2.txt", "file2", inf.mtime)

    # spaced
    ext3 = tmp_path / "ext3"
    inf = rf.getinfo("sub/with space/long fn.txt")
    rf.extract("sub/with space/long fn.txt", ext3)
    checkfile(ext3 / "sub/with space/long fn.txt", "long fn", inf.mtime)

    # unicode
    ext4 = tmp_path / "ext4"
    inf = rf.getinfo("sub/üȵĩöḋè/file.txt")
    rf.extract("sub/üȵĩöḋè/file.txt", ext4)
    checkfile(ext4 / "sub/üȵĩöḋè/file.txt", "file", inf.mtime)

    # dir only
    ext5 = tmp_path / "ext5"
    inf = rf.getinfo("sub/dir2")
    rf.extract("sub/dir2", ext5)
    assert os.listdir(ext5 / "sub") == ["dir2"]
    assert os.listdir(ext5 / "sub/dir2") == []
    checktime(ext5 / "sub/dir2", inf.mtime)

    # cwd
    ext6 = tmp_path / "ext6"
    os.mkdir(ext6)
    old = os.getcwd()
    try:
        os.chdir(ext6)
        rf.extract("sub/dir1")
        assert os.listdir(".") == ["sub"]
        assert os.listdir("sub") == ["dir1"]
        assert os.listdir("sub/dir1") == []
    finally:
        os.chdir(old)


@pytest.mark.parametrize("fn", [
    "test/files/rar3-subdirs.rar",
    "test/files/rar5-subdirs.rar",
])
def test_subdirs(fn, tmp_path):
    with rarfile.RarFile(fn) as rf:
        check_subdir(rf, tmp_path)


@pytest.mark.parametrize("fn", [
    "test/files/rar3-readonly-unix.rar",
    "test/files/rar3-readonly-win.rar",
    "test/files/rar5-readonly-unix.rar",
    "test/files/rar5-readonly-win.rar",
])
def test_readonly(fn, tmp_path):
    with rarfile.RarFile(fn) as rf:
        rf.extractall(tmp_path)

    assert os.access(tmp_path / "ro_dir/ro_file.txt", os.R_OK)
    assert not os.access(tmp_path / "ro_dir/ro_file.txt", os.W_OK)

    if sys.platform != "win32":
        assert os.access(tmp_path / "ro_dir", os.R_OK)
        assert not os.access(tmp_path / "ro_dir", os.W_OK)


@pytest.mark.parametrize("fn", [
    "test/files/rar3-symlink-unix.rar",
    "test/files/rar5-symlink-unix.rar",
])
def test_symlink(fn, tmp_path):
    with rarfile.RarFile(fn) as rf:
        rf.extractall(tmp_path)

        assert sorted(os.listdir(tmp_path)) == ["data.txt", "data_link", "random_link"]

        data = rf.getinfo("data.txt")
        data_link = rf.getinfo("data_link")
        random_link = rf.getinfo("random_link")

        assert not data.is_link()
        assert data_link.is_link()
        assert random_link.is_link()

        assert rf.read(data) == b"data\n"
        assert rf.read(data_link) == b"data.txt"
        assert rf.read(random_link) == b"../random123"

        assert os.path.isfile(tmp_path / "data.txt")
        assert os.path.islink(tmp_path / "data_link")
        assert os.path.islink(tmp_path / "random_link")

        assert os.readlink(tmp_path / "data_link") == "data.txt"
        assert os.readlink(tmp_path / "random_link") == "../random123"

