
from datetime import datetime

import rarfile


def test_load_vint():
    assert rarfile.load_vint(b"\x00", 0) == (0, 1)
    assert rarfile.load_vint(b"\x80\x01", 0) == (1<<7, 2)
    assert rarfile.load_vint(b"\x80\x80\x01", 0) == (1<<14, 3)
    assert rarfile.load_vint(b"\x80\x80\x80\x01", 0) == (1<<21, 4)
    assert rarfile.load_vint(b"\x80\x80\x80\x80\x01", 0) == (1<<28, 5)
    assert rarfile.load_vint(b"\x80\x80\x80\x80\x80\x01", 0) == (1<<35, 6)
    assert rarfile.load_vint(b"\x80" * 10 + b"\x01", 0) == (1<<70, 11)


def test_to_datetime():
    assert rarfile.to_datetime((2020,0,0,0,0,0)) == datetime(2020,1,1,0,0,0)
    assert rarfile.to_datetime((2020,60,60,60,60,60)) == datetime(2020,12,31,23,59,59)
    assert rarfile.to_datetime((2020,2,30,60,60,60)) == datetime(2020,2,29,23,59,59)
    assert rarfile.to_datetime((2021,2,30,60,60,60)) == datetime(2021,2,28,23,59,59)


def test_to_nsdatetime():
    base = datetime(2020,1,1,0,0,0, tzinfo=rarfile.UTC)
    assert rarfile.to_nsdatetime(base, 0) is base

    res = rarfile.to_nsdatetime(base, 1000)
    assert res == base.replace(microsecond=1)
    assert isinstance(res, datetime)
    assert res.isoformat(" ") == "2020-01-01 00:00:00.000001+00:00"

    res = rarfile.to_nsdatetime(base, 1001)
    assert isinstance(res, datetime)
    assert isinstance(res, rarfile.nsdatetime)
    assert res.microsecond == 1
    assert res.nanosecond == 1001
    assert res.isoformat(" ") == "2020-01-01 00:00:00.000001001+00:00"
    assert res.isoformat(" ", "auto") == "2020-01-01 00:00:00.000001001+00:00"
    assert res.isoformat(" ", "microseconds") == "2020-01-01 00:00:00.000001+00:00"

