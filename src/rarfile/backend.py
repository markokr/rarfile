import errno
import re
from subprocess import DEVNULL, PIPE, STDOUT, Popen

from . import config
from .errors import (
    BadRarFile, RarCannotExec, RarCRCError, RarCreateError, RarFatalError,
    RarLockedArchiveError, RarMemoryError, RarNoFilesError, RarOpenError,
    RarSignalExit, RarUnknownError, RarUserBreak, RarUserError,
    RarWarning, RarWriteError, RarWrongPassword,
)

__all__ = ('empty_read', 'custom_popen', 'check_returncode', 'ToolSetup', 'tool_setup')


def empty_read(src, size, blklen):
    """Read and drop fixed amount of data.
    """
    while size > 0:
        if size > blklen:
            res = src.read(blklen)
        else:
            res = src.read(size)
        if not res:
            raise BadRarFile("cannot load data")
        size -= len(res)


def custom_popen(cmd):
    """Disconnect cmd from parent fds, read only from stdout.
    """
    creationflags = 0x08000000 if config.WIN32 else 0  # CREATE_NO_WINDOW
    try:
        p = Popen(cmd, bufsize=0, stdout=PIPE, stderr=STDOUT, stdin=DEVNULL,
                  creationflags=creationflags)
    except OSError as ex:
        if ex.errno == errno.ENOENT:
            raise RarCannotExec("Unrar not installed?") from None
        if ex.errno == errno.EACCES or ex.errno == errno.EPERM:
            raise RarCannotExec("Cannot execute unrar") from None
        raise
    return p


def check_returncode(code, out, errmap):
    """Raise exception according to unrar exit code.
    """
    if code == 0:
        return

    if code > 0 and code < len(errmap):
        exc = errmap[code]
    elif code == 255:
        exc = RarUserBreak
    elif code < 0:
        exc = RarSignalExit
    else:
        exc = RarUnknownError

    # format message
    if out:
        msg = "%s [%d]: %s" % (exc.__doc__, code, out)
    else:
        msg = "%s [%d]" % (exc.__doc__, code)

    raise exc(msg)


class ToolSetup:
    def __init__(self, setup):
        self.setup = setup
        self.executable = None

    def check(self):
        if "executables" in self.setup:
            for varname in self.setup["executables"]:
                tool = getattr(config, varname, None)
                if tool is None:
                    continue
                cmdline = [tool] + list(self.setup["check_cmd"])
                try:
                    p = custom_popen(cmdline)
                    out, _ = p.communicate()
                    if p.returncode != 0:
                        continue
                    pattern = self.setup.get("check_output")
                    if pattern and not re.search(pattern, out.decode("utf8", errors="replace")):
                        continue
                    self.executable = tool
                    return True
                except RarCannotExec:
                    continue
            return False
        # Legacy single-executable path
        cmdline = self.get_cmdline("check_cmd", None)
        self.executable = cmdline[0]
        try:
            p = custom_popen(cmdline)
            out, _ = p.communicate()
            return p.returncode == 0
        except RarCannotExec:
            return False

    def open_cmdline(self, pwd, rarfn, filefn=None):
        cmdline = self.get_cmdline("open_cmd", pwd)
        cmdline.append(rarfn)
        if filefn:
            self.add_file_arg(cmdline, filefn)
        return cmdline

    def get_errmap(self):
        return self.setup["errmap"]

    def get_cmdline(self, key, pwd, nodash=False):
        if "executables" in self.setup:
            cmdline = [self.executable] + list(self.setup[key])
        else:
            cmdline = list(self.setup[key])
            cmdline[0] = getattr(config, cmdline[0], None)
        if key == "check_cmd":
            return cmdline
        self.add_password_arg(cmdline, pwd)
        if not nodash:
            cmdline.append("--")
        return cmdline

    def add_file_arg(self, cmdline, filename):
        cmdline.append(filename)

    def add_password_arg(self, cmdline, pwd):
        """Append password switch to commandline.
        """
        if pwd is not None:
            if not isinstance(pwd, str):
                pwd = pwd.decode("utf8")
            args = self.setup["password"]
            if args is None:
                tool = self.executable or self.setup["open_cmd"][0]
                raise RarCannotExec(f"{tool} does not support passwords")
            elif isinstance(args, str):
                cmdline.append(args + pwd)
            else:
                cmdline.extend(args)
                cmdline.append(pwd)
        else:
            cmdline.extend(self.setup["no_password"])


UNRAR_CONFIG = {
    "open_cmd": ("UNRAR_TOOL", "p", "-inul"),
    "check_cmd": ("UNRAR_TOOL", "-inul", "-?"),
    "password": "-p",
    "no_password": ("-p-",),
    # map return code to exception class, codes from rar.txt
    "errmap": [None,
               RarWarning, RarFatalError, RarCRCError, RarLockedArchiveError,    # 1..4
               RarWriteError, RarOpenError, RarUserError, RarMemoryError,        # 5..8
               RarCreateError, RarNoFilesError, RarWrongPassword]                # 9..11
}

# Problems with unar RAR backend:
# - Does not support RAR2 locked files [fails to read]
# - Does not support RAR5 Blake2sp hash [reading works]
UNAR_CONFIG = {
    "open_cmd": ("UNAR_TOOL", "-q", "-o", "-"),
    "check_cmd": ("UNAR_TOOL", "-version"),
    "password": ("-p",),
    "no_password": ("-p", ""),
    "errmap": [None],
}

# Problems with libarchive RAR backend:
# - Does not support solid archives.
# - Does not support password-protected archives.
# - Does not support RARVM-based compression filters.
BSDTAR_CONFIG = {
    "executables": ("BSDTAR_TOOL", "TAR_TOOL"),
    "open_cmd": ("-x", "--to-stdout", "-f"),
    "check_cmd": ("--version",),
    "check_output": "bsdtar|libarchive",
    "password": None,
    "no_password": (),
    "errmap": [None],
}

SEVENZIP_CONFIG = {
    "executables": ("SEVENZIP_TOOL", "SEVENZIP2_TOOL"),
    "open_cmd": ("e", "-so", "-bb0"),
    "check_cmd": ("i",),
    "check_output": "Rar3",  # rar plugin appears in "Codec" not "Format"
    "password": "-p",
    "no_password": ("-p",),
    "errmap": [None,
               RarWarning, RarFatalError, None, None,           # 1..4
               None, None, RarUserError, RarMemoryError]        # 5..8
}

CURRENT_SETUP = None


def tool_setup(unrar=True, unar=True, bsdtar=True, sevenzip=True, force=False):
    """Pick a tool, return cached ToolSetup.
    """
    global CURRENT_SETUP
    if force:
        CURRENT_SETUP = None
    if CURRENT_SETUP is not None:
        return CURRENT_SETUP
    lst = []
    if unrar:
        lst.append(UNRAR_CONFIG)
    if unar:
        lst.append(UNAR_CONFIG)
    if sevenzip:
        lst.append(SEVENZIP_CONFIG)
    if bsdtar:
        lst.append(BSDTAR_CONFIG)

    for conf in lst:
        setup = ToolSetup(conf)
        if setup.check():
            CURRENT_SETUP = setup
            break
    if CURRENT_SETUP is None:
        raise RarCannotExec("Cannot find working tool")
    return CURRENT_SETUP
