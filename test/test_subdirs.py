"""Alt tool tests
"""

import os

import rarfile


def checkfile(fn, data):
    with open(fn, "r") as f:
        got = f.read()
        assert got.strip() == data


def check_subdir(rf, tmp_path):
    # pre-mkdir
    ext1 = tmp_path / "ext1"
    inf = rf.getinfo("sub/dir1/file1.txt")
    os.mkdir(ext1)
    rf.extract(inf, ext1)
    assert sorted(os.listdir(tmp_path)) == ["ext1"]
    assert os.listdir(ext1 / "sub") == ["dir1"]
    checkfile(ext1 / "sub/dir1/file1.txt", "file1")

    # no mkdir
    ext2 = tmp_path / "ext2"
    rf.extract("sub/dir2/file2.txt", ext2)
    assert sorted(os.listdir(tmp_path)) == ["ext1", "ext2"]
    assert os.listdir(ext2 / "sub") == ["dir2"]
    checkfile(ext2 / "sub/dir2/file2.txt", "file2")

    # spaced
    ext3 = tmp_path / "ext3"
    rf.extract("sub/with space/long fn.txt", ext3)
    checkfile(ext3 / "sub/with space/long fn.txt", "long fn")

    # unicode
    ext4 = tmp_path / "ext4"
    rf.extract("sub/üȵĩöḋè/file.txt", ext4)
    checkfile(ext4 / "sub/üȵĩöḋè/file.txt", "file")

    # dir only
    ext5 = tmp_path / "ext5"
    rf.extract("sub/dir2", ext5)
    assert os.listdir(ext5 / "sub") == ["dir2"]
    assert os.listdir(ext5 / "sub/dir2") == []

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

