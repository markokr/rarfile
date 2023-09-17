"""Alt tool tests
"""

import sys
import os

import pytest

import rarfile


def have_tool(name):
    for dn in os.get_exec_path():
        if os.path.isfile(os.path.join(dn, name)):
            return True
        if os.path.isfile(os.path.join(dn, name + ".exe")):
            return True
    return False


def tool_setup(unrar=False, unar=False, bsdtar=False, sevenzip=False, sevenzip2=False):
    rarfile.FORCE_TOOL = True
    rarfile.tool_setup(unrar=unrar, unar=unar, bsdtar=bsdtar,
                       sevenzip=sevenzip, sevenzip2=sevenzip2,
                       force=True)


def install_unrar_tool():
    tool_setup(unrar=True)


def install_unar_tool():
    tool_setup(unar=True)


def install_bsdtar_tool():
    tool_setup(bsdtar=True)


def install_7z_tool():
    tool_setup(sevenzip=True)


def install_7zz_tool():
    tool_setup(sevenzip2=True)


def uninstall_alt_tool():
    rarfile.FORCE_TOOL = False
    rarfile.tool_setup(force=True)


def test_read_rar3():
    with rarfile.RarFile("test/files/seektest.rar") as rf:
        for fn in rf.namelist():
            rf.read(fn)


def test_read_vols():
    with rarfile.RarFile("test/files/rar3-old.rar") as rf:
        for fn in rf.namelist():
            rf.read(fn) # old
    with rarfile.RarFile("test/files/rar3-vols.part1.rar") as rf:
        for fn in rf.namelist():
            rf.read(fn) # rar3-new
    with rarfile.RarFile("test/files/rar5-vols.part1.rar") as rf:
        for fn in rf.namelist():
            rf.read(fn) # rar5


def test_unrar_tool():
    install_unrar_tool()
    try:
        test_read_rar3()
        test_read_vols()

        with rarfile.RarFile("test/files/rar3-comment-plain.rar") as rf:
            rf.read("file1.txt")
            rf.read("file2.txt")

        with rarfile.RarFile("test/files/rar3-comment-psw.rar") as rf:
            rf.setpassword("password")
            rf.read("file1.txt")
    finally:
        uninstall_alt_tool()


@pytest.mark.skipif(sys.platform == "win32", reason="unar not available on Windows")
@pytest.mark.skipif(not have_tool(rarfile.UNAR_TOOL), reason="unar not installed")
def test_unar_tool():
    install_unar_tool()
    try:
        test_read_rar3()
        test_read_vols()

        with rarfile.RarFile("test/files/rar3-comment-plain.rar") as rf:
            rf.read("file1.txt")
            rf.read("file2.txt")

        with rarfile.RarFile("test/files/rar3-comment-psw.rar") as rf:
            rf.setpassword("password")
            rf.read("file1.txt")
    finally:
        uninstall_alt_tool()


@pytest.mark.skipif(not have_tool(rarfile.BSDTAR_TOOL), reason="bsdtar not installed")
def test_bsdtar_tool():
    install_bsdtar_tool()
    try:
        #test_read_rar3()
        #test_read_vols()

        with rarfile.RarFile("test/files/rar3-comment-plain.rar") as rf:
            rf.read("file1.txt")
            rf.read("file2.txt")

        with pytest.raises(rarfile.RarCannotExec):
            with rarfile.RarFile("test/files/rar3-comment-psw.rar") as rf:
                rf.setpassword("password")
                rf.read("file1.txt")
    finally:
        uninstall_alt_tool()


@pytest.mark.skipif(not have_tool(rarfile.SEVENZIP_TOOL), reason="7z not installed")
def test_7z_tool():
    install_7z_tool()
    try:
        #test_read_rar3()
        test_read_vols()

        with rarfile.RarFile("test/files/rar3-comment-plain.rar") as rf:
            rf.read("file1.txt")
            rf.read("file2.txt")

        with rarfile.RarFile("test/files/rar3-comment-psw.rar") as rf:
            rf.setpassword("password")
            rf.read("file1.txt")
    finally:
        uninstall_alt_tool()


@pytest.mark.skipif(not have_tool(rarfile.SEVENZIP2_TOOL), reason="7zz not installed")
def test_7zz_tool():
    install_7zz_tool()
    try:
        #test_read_rar3()
        test_read_vols()

        with rarfile.RarFile("test/files/rar3-comment-plain.rar") as rf:
            rf.read("file1.txt")
            rf.read("file2.txt")

        with rarfile.RarFile("test/files/rar3-comment-psw.rar") as rf:
            rf.setpassword("password")
            rf.read("file1.txt")
    finally:
        uninstall_alt_tool()


# test popen errors

def test_popen_fail():
    with pytest.raises(rarfile.RarCannotExec):
        rarfile.custom_popen(["missing-unrar-exe"])

    if sys.platform != "win32":
        with pytest.raises(rarfile.RarCannotExec):
            rarfile.custom_popen(["./test/files/rar5-blake.rar.exp"])


def test_check_returncode():
    errmap = rarfile.UNRAR_CONFIG["errmap"]

    assert not rarfile.check_returncode(0, "", errmap)

    with pytest.raises(rarfile.RarFatalError):
        rarfile.check_returncode(2, "x", errmap)
    with pytest.raises(rarfile.RarUnknownError):
        rarfile.check_returncode(100, "", errmap)
    with pytest.raises(rarfile.RarUserBreak):
        rarfile.check_returncode(255, "", errmap)
    with pytest.raises(rarfile.RarSignalExit):
        rarfile.check_returncode(-11, "", errmap)

    errmap = rarfile.UNAR_CONFIG["errmap"]
    with pytest.raises(rarfile.RarUnknownError):
        rarfile.check_returncode(2, "", errmap)


# own cli tests

def cli(*args):
    try:
        rarfile.main(args)
        return 0
    except SystemExit as ex:
        return int(ex.code)
    except Exception as ex:
        sys.stderr.write(str(ex) + "\n")
        return 1


def test_cli_list(capsys):
    assert cli("-l", "test/files/rar3-old.rar") == 0
    res = capsys.readouterr()
    assert "bigfile" in res.out


def test_cli_testrar(capsys):
    assert cli("-t", "test/files/rar3-old.rar") == 0
    res = capsys.readouterr()
    assert not res.err


def test_cli_extract(capsys, tmp_path):
    assert cli("-e", "test/files/rar3-old.rar", str(tmp_path)) == 0
    res = capsys.readouterr()
    assert not res.err


def test_cli_help(capsys):
    assert cli("--help") == 0
    res = capsys.readouterr()
    assert "option" in res.out

