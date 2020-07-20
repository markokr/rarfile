"""Alt tool tests
"""

import os

import rarfile


def checkfile(fn, data):
    with open(fn, "r") as f:
        got = f.read()
        assert got.strip() == data

def test_subdir_rar3(tmp_path):
    with rarfile.RarFile('test/files/rar3-subdirs.rar') as rf:

        # pre-mkdir
        ext1 = tmp_path / "ext1"
        inf = rf.getinfo("sub")
        os.mkdir(ext1)
        rf.extract(inf, ext1)
        checkfile(ext1 / "sub/dir1/file1.txt", "file1")
        checkfile(ext1 / "sub/dir2/file2.txt", "file2")

        # no mkdir
        ext2 = tmp_path / "ext2"
        rf.extract("sub", ext2)
        checkfile(ext2 / "sub/dir1/file1.txt", "file1")
        checkfile(ext2 / "sub/dir2/file2.txt", "file2")

        # spaced
        ext3 = tmp_path / "ext3"
        rf.extract("sub/with space", ext3)
        checkfile(ext3 / "sub/with space/long fn.txt", "long fn")
        checkfile(ext3 / "sub/with space/long fn.txt", "long fn")

        # unicode
        ext4 = tmp_path / "ext4"
        rf.extract("sub/üȵĩöḋè", ext4)
        checkfile(ext4 / "sub/üȵĩöḋè/file.txt", "file")


