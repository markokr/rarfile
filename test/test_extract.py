"""Extract tests.
"""

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
    assert san_win32("z<>*?:") == "z_____"

