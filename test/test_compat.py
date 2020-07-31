"""Test zipfile compat.
"""

import inspect
import sys
import zipfile

import pytest

import rarfile

# dont fail on new python by default
_VERS = [(3, 6), (3, 7), (3, 8)]

_UNSUPPORTED = sys.version_info[:2] not in _VERS

_ignore = set([
    "detach",
    "peek",
    "read1",
    "readinto1",

    "seek",

    # no kwargs
    "readinto",
    "readline",
    "truncate",
    "write",

    # random
    "FileHeader",
    "from_file",
    "testzip",
    "writestr",
])


def load_cls_names(maincls):
    assert inspect.isclass(maincls)
    res = {}
    for cls in inspect.getmro(maincls):
        for name, val in inspect.getmembers(cls):
            if name not in res:
                res[name] = val
    return res


def cleansig(sig):
    res = str(sig).replace(", /", "")
    if "*" in res:
        res = res.split(", *")[0] + ")"
    return res


def compare(rmaincls, zmaincls):
    znames = load_cls_names(zmaincls)
    rnames = load_cls_names(rmaincls)
    for name, zval in znames.items():
        if not inspect.isroutine(zval) or name[0] == "_" or name in _ignore:
            continue
        assert name in rnames, "member not found: \"%s\"" % name

        rval = rnames[name]
        zsig = inspect.signature(zval)
        rsig = inspect.signature(rval)

        zsigstr = cleansig(zsig)
        rsigstr = cleansig(rsig)
        assert zsigstr == rsigstr, "sig differs: %s.%s%s != %s.%s%s" % (
            rmaincls.__name__, name, rsigstr,
            zmaincls.__name__, name, zsigstr)


@pytest.mark.skipif(_UNSUPPORTED, reason="Unsupported for sig checks")
def test_cmp_zipfile():
    compare(rarfile.RarFile, zipfile.ZipFile)


@pytest.mark.skipif(_UNSUPPORTED, reason="Unsupported for sig checks")
def test_cmp_zipextfile():
    compare(rarfile.RarExtFile, zipfile.ZipExtFile)


@pytest.mark.skipif(_UNSUPPORTED, reason="Unsupported for sig checks")
def test_cmp_zipinfo():
    compare(rarfile.RarInfo, zipfile.ZipInfo)

