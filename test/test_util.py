
# pylint: disable=comparison-with-itself,unneeded-not

from datetime import datetime, timedelta, timezone

import rarfile


def test_load_vint():
    assert rarfile.load_vint(b"\x00", 0) == (0, 1)
    assert rarfile.load_vint(b"\x80\x01", 0) == (1 << 7, 2)
    assert rarfile.load_vint(b"\x80\x80\x01", 0) == (1 << 14, 3)
    assert rarfile.load_vint(b"\x80\x80\x80\x01", 0) == (1 << 21, 4)
    assert rarfile.load_vint(b"\x80\x80\x80\x80\x01", 0) == (1 << 28, 5)
    assert rarfile.load_vint(b"\x80\x80\x80\x80\x80\x01", 0) == (1 << 35, 6)
    assert rarfile.load_vint(b"\x80" * 10 + b"\x01", 0) == (1 << 70, 11)


def test_to_datetime():
    assert rarfile.to_datetime((2020, 0, 0, 0, 0, 0)) == datetime(2020, 1, 1, 0, 0, 0)
    assert rarfile.to_datetime((2020, 60, 60, 60, 60, 60)) == datetime(2020, 12, 31, 23, 59, 59)
    assert rarfile.to_datetime((2020, 2, 30, 60, 60, 60)) == datetime(2020, 2, 29, 23, 59, 59)
    assert rarfile.to_datetime((2021, 2, 30, 60, 60, 60)) == datetime(2021, 2, 28, 23, 59, 59)


def test_to_nsdatetime():
    base = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
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


def test_nsdatetime_cmp():
    nsdatetime = rarfile.nsdatetime

    n1 = nsdatetime(2000, 1, 1, 9, 15, 30, nanosecond=100200300, tzinfo=timezone.utc)
    n2 = nsdatetime(2000, 1, 1, 9, 15, 30, nanosecond=100200301, tzinfo=timezone.utc)
    n3 = nsdatetime(2000, 1, 1, 9, 15, 30, nanosecond=100200402, tzinfo=timezone.utc)

    d1 = datetime(2000, 1, 1, 9, 15, 30, 100100, timezone.utc)
    d2 = datetime(2000, 1, 1, 9, 15, 30, 100200, timezone.utc)
    d3 = datetime(2000, 1, 1, 9, 15, 30, 100300, timezone.utc)

    n2x = n2 + timedelta(seconds=0)
    assert not isinstance(n2x, nsdatetime)
    assert not hasattr(n2x, "_nanoseconds")
    assert n2x == d2
    assert hash(n2x) == hash(d2)
    assert hash(n2) != hash(d2)

    # compare nsdatetime only
    n1c = n1.replace()
    assert n1 == n1
    assert n1 == n1c
    assert n1 <= n1c
    assert n1 >= n1c
    assert n1 < n2
    assert n1 <= n2
    assert n1 != n2
    assert not n1 == n2
    assert n2 > n1
    assert n2 >= n1
    assert not n2 < n1
    assert not n1 > n2

    # mixed eq
    assert not d2 == n2
    assert not n2 == d2
    assert d2 != n2
    assert n2 != d2

    # mixed gt
    assert n2 > d2
    assert d3 > n2
    assert not d2 > n3
    assert not n2 > d3

    # mixed lt
    assert d1 < n2 < d3


def test_nsdatetime_astimezone():
    nsdatetime = rarfile.nsdatetime
    X1 = timezone(timedelta(hours=1), "X1")

    n1 = nsdatetime(2000, 1, 1, 9, 15, 30, nanosecond=100200402, tzinfo=timezone.utc)
    n2 = n1.astimezone(X1)
    assert n2.nanosecond == n1.nanosecond
    assert (n1.year, n1.month, n1.day) == (n2.year, n2.month, n2.day)
    assert (n1.hour, n1.minute, n1.second) == (n2.hour - 1, n2.minute, n2.second)

