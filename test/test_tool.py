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
    with rarfile.RarFile("test/files/seektest.rar") as rf:
        for fn in rf.namelist():
            rf.read(fn)


def test_read_rar3_old():
    with rarfile.RarFile("test/files/rar3-old.rar") as rf:
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
        with rarfile.RarFile("test/files/rar3-old.rar") as rf:
            for fn in rf.namelist():
                rf.read(fn)
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
    assert "optional" in res.out

