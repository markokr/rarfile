"""Format details.
"""

from datetime import datetime

import pytest

import rarfile


def render_date(dt):
    if isinstance(dt, datetime):
        return dt.isoformat("T")
    elif isinstance(dt, tuple):
        return "%04d-%02d-%02d %02d:%02d:%02d" % dt
    else:
        return dt


def mkitem(**kwargs):
    res = {}
    for k in kwargs:
        if kwargs[k] is not None:
            res[k] = kwargs[k]
    return res


def dumparc(rf):
    res = []
    for item in rf.infolist():
        info = mkitem(fn=item.filename,
                      file_size=item.file_size,
                      compress_size=item.compress_size,
                      CRC=item.CRC,
                      date_time=render_date(item.date_time),
                      arctime=render_date(item.arctime),
                      mtime=render_date(item.mtime),
                      atime=render_date(item.atime),
                      ctime=render_date(item.ctime),
                      comment=item.comment,
                      extract_version=item.extract_version,
                      compress_type=item.compress_type,
                      mode=item.mode,
                      host_os=item.host_os)
        res.append(info)
    return res


def diffs(a, b):
    if len(a) != len(b):
        return "Different lengths"
    problems = []
    for i, xa in enumerate(a):
        xb = b[i]
        for k in xa:
            if k not in xb:
                problems.append("NewKey(%d,%s)=%r" % (i, k, xa[k]))
        for k in xb:
            if k not in xa:
                problems.append("MissingKey(%d,%s)=%r" % (i, k, xb[k]))
        for k in xa:
            if k in xb and xa[k] != xb[k]:
                problems.append("ErrValue(%d,%s):got=%r/exp=%r" % (i, k, xa[k], xb[k]))
    return "; ".join(problems)


def cmp_struct(a, b):
    assert a == b, diffs(a, b)

#
# test start
#


@pytest.mark.skipif(not rarfile._have_crypto, reason="No crypto")
def test_rar3_header_encryption():
    r = rarfile.RarFile("test/files/rar3-comment-hpsw.rar", "r")
    assert r.needs_password() is True
    assert r.comment is None
    assert r.namelist() == []

    r.setpassword("password")
    assert r.needs_password() is True
    assert r.namelist() == ["file1.txt", "file2.txt"]
    assert r.comment is not None
    assert r.comment == "RARcomment\n"


@pytest.mark.skipif(not rarfile._have_crypto, reason="No crypto")
def test_rar5_header_encryption():
    r = rarfile.RarFile("test/files/rar5-hpsw.rar")
    assert r.needs_password() is True
    assert r.comment is None
    assert r.namelist() == []

    r.setpassword("password")
    assert r.needs_password() is True
    assert r.namelist() == ["stest1.txt", "stest2.txt"]
    assert r.comment is not None
    assert r.comment == "RAR5 archive - hdr-password\n"
    r.close()


def get_vol_info(extver=20, tz="", hr="11"):
    return [
        mkitem(CRC=1352324940,
               date_time="2016-05-24 %s:42:37%s" % (hr, ""),
               mtime="2016-05-24T%s:42:37%s" % (hr, tz),
               compress_type=48,
               compress_size=205000,
               extract_version=extver,
               file_size=205000,
               mode=33204,
               host_os=3,
               fn="vols/bigfile.txt"),
        mkitem(CRC=3498712966,
               date_time="2016-05-24 %s:42:43%s" % (hr, ""),
               mtime="2016-05-24T%s:42:43%s" % (hr, tz),
               extract_version=extver,
               compress_type=48,
               compress_size=2050,
               file_size=2050,
               mode=33204,
               host_os=3,
               fn="vols/smallfile.txt")]


def test_rar3_vols():
    r = rarfile.RarFile("test/files/rar3-vols.part1.rar")
    assert r.needs_password() is False
    assert r.comment is None
    assert r.strerror() is None
    cmp_struct(dumparc(r), get_vol_info())
    assert r.volumelist() == [
        "test/files/rar3-vols.part1.rar",
        "test/files/rar3-vols.part2.rar",
        "test/files/rar3-vols.part3.rar"]
    with pytest.raises(rarfile.NeedFirstVolume):
        rarfile.RarFile("test/files/rar3-vols.part2.rar")


def test_rar3_oldvols():
    r = rarfile.RarFile("test/files/rar3-old.rar")
    assert r.needs_password() is False
    assert r.comment is None
    assert r.strerror() is None
    cmp_struct(dumparc(r), get_vol_info())
    assert r.volumelist() == [
        "test/files/rar3-old.rar",
        "test/files/rar3-old.r00",
        "test/files/rar3-old.r01"]
    with pytest.raises(rarfile.NeedFirstVolume):
        rarfile.RarFile("test/files/rar3-old.r00")


def test_rar5_vols():
    r = rarfile.RarFile("test/files/rar5-vols.part1.rar")
    assert r.needs_password() is False
    assert r.comment is None
    assert r.strerror() is None
    cmp_struct(dumparc(r), get_vol_info(50, "+00:00", "08"))
    assert r.volumelist() == [
        "test/files/rar5-vols.part1.rar",
        "test/files/rar5-vols.part2.rar",
        "test/files/rar5-vols.part3.rar"]
    with pytest.raises(rarfile.NeedFirstVolume):
        rarfile.RarFile("test/files/rar5-vols.part2.rar")


def expect_ctime(mtime, ctime):
    return [mkitem(
        mtime=mtime,
        date_time=mtime.split(".")[0].replace("T", " "),
        ctime=ctime,
        compress_size=0,
        file_size=0,
        CRC=0,
        fn="afile.txt",
        extract_version=29,
        compress_type=48,
        mode=32,
        host_os=2)]


def test_rar3_ctime0():
    r = rarfile.RarFile("test/files/ctime0.rar")
    cmp_struct(dumparc(r), expect_ctime("2011-05-10T21:28:47.899345100", None))


def test_rar3_ctime1():
    r = rarfile.RarFile("test/files/ctime1.rar")
    cmp_struct(dumparc(r), expect_ctime("2011-05-10T21:28:47.899345100", "2011-05-10T21:28:47"))


def test_rar3_ctime2():
    r = rarfile.RarFile("test/files/ctime2.rar")
    cmp_struct(dumparc(r), expect_ctime("2011-05-10T21:28:47.899345100", "2011-05-10T21:28:47.897843200"))


def test_rar3_ctime3():
    r = rarfile.RarFile("test/files/ctime3.rar")
    cmp_struct(dumparc(r), expect_ctime("2011-05-10T21:28:47.899345100", "2011-05-10T21:28:47.899328"))


def test_rar3_ctime4():
    r = rarfile.RarFile("test/files/ctime4.rar")
    cmp_struct(dumparc(r), expect_ctime("2011-05-10T21:28:47.899345100", "2011-05-10T21:28:47.899345100"))


def test_rar5_ctime5():
    r = rarfile.RarFile("test/files/ctime5.rar")
    inf = r.getinfo("timed.txt")
    assert inf.mtime.isoformat() == "2020-07-30T20:26:59.677675904+00:00"
    assert inf.ctime.isoformat() == "2020-07-30T20:28:19.398867888+00:00"
    assert inf.atime.isoformat() == "2020-07-30T20:27:10.121196721+00:00"


def test_rar5_times():
    r = rarfile.RarFile("test/files/rar5-times.rar")
    cmp_struct(dumparc(r), [mkitem(
        fn="stest1.txt",
        file_size=2048,
        compress_size=55,
        compress_type=rarfile.RAR_M3,
        extract_version=50,
        host_os=rarfile.RAR_OS_UNIX,
        mode=33188,
        date_time="2011-06-12 09:53:33",
        mtime="2011-06-12T09:53:33+00:00",
        atime="2016-05-22T09:12:36+00:00",
        CRC=3317163682
    )])


def test_oldvols():
    assert rarfile._next_oldvol("qq00.part0.rar") == "qq00.part0.r00"
    assert rarfile._next_oldvol("qq00.part0.r00") == "qq00.part0.r01"
    assert rarfile._next_oldvol("qq00.part0.r29") == "qq00.part0.r30"
    assert rarfile._next_oldvol("qq00.part0.r99") == "qq00.part0.s00"


def test_newvols():
    assert rarfile._next_newvol("qq00.part0.rar") == "qq00.part1.rar"
    assert rarfile._next_newvol("qq00.part09.rar") == "qq00.part10.rar"
    assert rarfile._next_newvol("qq00.part99.rar") == "qq00.paru00.rar"


def test_newvols_err():
    with pytest.raises(rarfile.BadRarName):
        rarfile._next_newvol("xx.rar")


@pytest.mark.parametrize("fn", ["test/files/rar3-versions.rar", "test/files/rar5-versions.rar"])
def test_versions(fn):
    with rarfile.RarFile(fn) as rf:
        assert rf.namelist() == ["versioned.txt"]

