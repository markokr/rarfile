"""Alt tool tests
"""

import sys

import pytest
import rarfile


def install_unar_tool():
    rarfile.tool_setup(unrar=False, unar=True, bsdtar=False, force=True)


def install_bsdtar_tool():
    rarfile.tool_setup(unrar=False, unar=False, bsdtar=True, force=True)


def uninstall_alt_tool():
    rarfile.tool_setup(force=True)


def test_read_rar3():
    with rarfile.RarFile('test/files/seektest.rar') as rf:
        for fn in rf.namelist():
            rf.read(fn)


def test_read_rar3_old():
    with rarfile.RarFile('test/files/rar3-old.rar') as rf:
        for fn in rf.namelist():
            rf.read(fn)


@pytest.mark.skipif(sys.platform == "win32", reason="unar not available on Windows")
def test_unar_tool():
    install_unar_tool()
    try:
        test_read_rar3()
        test_read_rar3_old()
    finally:
        uninstall_alt_tool()


def test_bsdtar_tool():
    install_bsdtar_tool()
    try:
        with rarfile.RarFile('test/files/rar3-old.rar') as rf:
            for fn in rf.namelist():
                rf.read(fn)
    finally:
        uninstall_alt_tool()

