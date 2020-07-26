"""Extract tests.
"""

import os
from datetime import datetime

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


def checktime(fn, timestamp):
    # cannot check subsecond precision as filesystem may not support it
    st = os.stat(fn)
    mtime = datetime.fromtimestamp(st.st_mtime, rarfile.UTC)
    mtime = mtime.isoformat(" ", "seconds").split("+")[0]
    assert timestamp == mtime


def checkfile(fn, data, timestamp=None):
    with open(fn, "r") as f:
        got = f.read()
        assert got.strip() == data

    checktime(fn, timestamp)


def check_subdir(rf, tmp_path):
    # pre-mkdir
    ext1 = tmp_path / "ext1"
    inf = rf.getinfo("sub/dir1/file1.txt")
    os.mkdir(ext1)
    rf.extract(inf, ext1)
    assert sorted(os.listdir(tmp_path)) == ["ext1"]
    assert os.listdir(ext1 / "sub") == ["dir1"]
    checkfile(ext1 / "sub/dir1/file1.txt", "file1", "2020-07-20 18:01:33")

    # no mkdir
    ext2 = tmp_path / "ext2"
    rf.extract("sub/dir2/file2.txt", ext2)
    assert sorted(os.listdir(tmp_path)) == ["ext1", "ext2"]
    assert os.listdir(ext2 / "sub") == ["dir2"]
    checkfile(ext2 / "sub/dir2/file2.txt", "file2", "2020-07-20 18:01:44")

    # spaced
    ext3 = tmp_path / "ext3"
    rf.extract("sub/with space/long fn.txt", ext3)
    checkfile(ext3 / "sub/with space/long fn.txt", "long fn", "2020-07-20 18:02:17")

    # unicode
    ext4 = tmp_path / "ext4"
    rf.extract("sub/üȵĩöḋè/file.txt", ext4)
    checkfile(ext4 / "sub/üȵĩöḋè/file.txt", "file", "2020-07-20 18:07:00")

    # dir only
    ext5 = tmp_path / "ext5"
    rf.extract("sub/dir2", ext5)
    assert os.listdir(ext5 / "sub") == ["dir2"]
    assert os.listdir(ext5 / "sub/dir2") == []
    checktime(ext5 / "sub/dir2", "2020-07-20 18:01:44")

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


def test_subdir_rar3(tmp_path):
    with rarfile.RarFile('test/files/rar3-subdirs.rar') as rf:
        check_subdir(rf, tmp_path)


def test_subdir_rar5(tmp_path):
    with rarfile.RarFile('test/files/rar5-subdirs.rar') as rf:
        check_subdir(rf, tmp_path)

