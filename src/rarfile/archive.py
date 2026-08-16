"""Main archive object.
"""

import io
import os
import shutil
import sys
import warnings
from collections.abc import Callable, Iterable, Iterator, Sequence
from pathlib import Path
from types import TracebackType
from typing import IO, Literal

from . import config
from .backend import empty_read
from .bits import (
    DOS_MODE_READONLY, RAR5_ID, RAR5_XREDIR_ISDIR,
    RAR5_XREDIR_WINDOWS_JUNCTION, RAR_FILE_DIRECTORY, RAR_ID,
    RAR_OS_MSDOS, RAR_OS_UNIX, RAR_OS_WIN32, RAR_V3, RAR_V5,
)
from .errors import (
    BadRarFile, BadSymLinkError, NotRarFile,
    PasswordRequired, UnsupportedWarning,
)
from .format import RAR3Parser, RAR5Parser
from .info import RarEntry, RarInfo
from .stream import RarExtFile
from .utils import (
    FileLike, PathLike, XFile, is_filelike, sanitize_filename, to_nsecs,
)

# export only interesting items
__all__ = ("get_rar_version", "is_rarfile", "is_rarfile_sfx", "RarFile")


def _find_sfx_header(xfile: PathLike | FileLike) -> tuple[int, int]:
    sig = RAR_ID[:-1]
    buf = io.BytesIO()
    steps = (64, config.SFX_MAX_SIZE)

    with XFile(xfile) as fd:
        for step in steps:
            data = fd.read(step)
            if not data:
                break
            buf.write(data)
            curdata = buf.getvalue()
            findpos = 0
            while True:
                pos = curdata.find(sig, findpos)
                if pos < 0:
                    break
                if curdata[pos:pos + len(RAR_ID)] == RAR_ID:
                    return RAR_V3, pos
                if curdata[pos:pos + len(RAR5_ID)] == RAR5_ID:
                    return RAR_V5, pos
                findpos = pos + len(sig)
        fd.restore_pos()
    return 0, 0


##
## Public interface
##


def get_rar_version(xfile: PathLike | FileLike) -> int:
    """Check quickly whether file is rar archive.
    """
    with XFile(xfile) as fd:
        buf = fd.read(len(RAR5_ID))
        fd.restore_pos()
    if buf.startswith(RAR_ID):
        return RAR_V3
    elif buf.startswith(RAR5_ID):
        return RAR_V5
    return 0


def is_rarfile(xfile: PathLike | FileLike) -> bool:
    """Check quickly whether file is rar archive.
    """
    try:
        return get_rar_version(xfile) > 0
    except OSError:
        # File not found or not accessible, ignore
        return False


def is_rarfile_sfx(xfile: PathLike | FileLike) -> bool:
    """Check whether file is rar archive with support for SFX.

    It will read 2M from file.
    """
    return _find_sfx_header(xfile)[0] > 0


class RarFile:
    """Parse RAR structure, provide access to files in archive.

    Parameters:

        file
            archive file name or file-like object.
        mode
            only "r" is supported.
        charset
            fallback charset to use, if filenames are not already Unicode-enabled.
        info_callback
            debug callback, gets to see all archive entries.
        crc_check
            set to False to disable CRC checks
        errors
            Either "stop" to quietly stop parsing on errors,
            or "strict" to raise errors.  Default is "stop".
        part_only
            If True, read only single file and allow it to be middle-part
            of multi-volume archive.

            .. versionadded:: 4.0
    """

    #: File name, if available.  Unicode string or None.
    filename: str | None = None

    #: Archive comment.  Unicode string or None.
    comment: str | None = None

    _file_parser: RAR3Parser | RAR5Parser | None = None

    def __init__(self, file: str | Path | FileLike,
                 mode: str = "r",
                 charset: str | None = None,
                 info_callback: Callable[[RarEntry], None] | None = None,
                 crc_check: bool = True,
                 errors: Literal["stop", "strict"] = "stop",
                 part_only: bool = False):
        if is_filelike(file):
            self.filename = getattr(file, "name", None)
        else:
            if isinstance(file, Path):
                file = str(file)
            self.filename = file
        self._rarfile: str | FileLike = file

        self._charset = charset or config.DEFAULT_CHARSET
        self._info_callback = info_callback
        self._crc_check = crc_check
        self._part_only = part_only
        self._password: str | None = None
        self._file_parser = None

        if errors == "stop":
            self._strict = False
        elif errors == "strict":
            self._strict = True
        else:
            raise ValueError("Invalid value for errors= parameter.")

        if mode != "r":
            raise NotImplementedError("RarFile supports only mode=r")

        self._parse()

    def __enter__(self) -> "RarFile":
        """Open context."""
        return self

    def __exit__(self, typ: type[BaseException] | None, value: BaseException | None,
                 traceback: TracebackType | None) -> None:
        """Exit context."""
        self.close()

    def __iter__(self) -> Iterator[RarInfo]:
        """Iterate over members."""
        return iter(self.infolist())

    def setpassword(self, pwd: str | None) -> None:
        """Sets the password to use when extracting.
        """
        self._password = pwd
        if self._file_parser:
            if self._file_parser.has_header_encryption():
                self._file_parser = None
        if not self._file_parser:
            self._parse()
        else:
            self._file_parser.setpassword(self._password)

    def needs_password(self) -> bool:
        """Returns True if any archive entries require password for extraction.
        """
        assert self._file_parser is not None
        return self._file_parser.needs_password()

    def is_solid(self) -> bool:
        """Returns True if archive uses solid compression.

        .. versionadded:: 4.2
        """
        assert self._file_parser is not None
        return self._file_parser.is_solid()

    def namelist(self) -> list[str]:
        """Return list of filenames in archive.
        """
        names: list[str] = []
        for f in self.infolist():
            names.append(f.filename)
        return names

    def infolist(self) -> Sequence[RarInfo]:
        """Return RarInfo objects for all files/directories in archive.
        """
        if self._file_parser is None:
            return []
        return self._file_parser.infolist()

    def volumelist(self) -> Sequence[PathLike | FileLike]:
        """Returns filenames of archive volumes.

        In case of single-volume archive, the list contains
        just the name of main archive file.
        """
        if self._file_parser is None:
            return []
        return self._file_parser.volumelist()

    def getinfo(self, name: str | Path | RarInfo) -> RarInfo:
        """Return RarInfo for file.
        """
        assert self._file_parser is not None
        return self._file_parser.getinfo(name)

    def getinfo_orig(self, name: str | Path | RarInfo) -> RarInfo:
        """Return RarInfo for file source.

        RAR5: if name is hard-linked or copied file,
        returns original entry with original filename.

        .. versionadded:: 4.1
        """
        assert self._file_parser is not None
        return self._file_parser.getinfo_orig(name)

    def open(self, name: str | Path | RarInfo, mode: str = "r", pwd: str | None = None) -> RarExtFile:
        """Returns file-like object (:class:`RarExtFile`) from where the data can be read.

        The object implements :class:`io.RawIOBase` interface, so it can
        be further wrapped with :class:`io.BufferedReader`
        and :class:`io.TextIOWrapper`.

        On older Python where io module is not available, it implements
        only .read(), .seek(), .tell() and .close() methods.

        The object is seekable, although the seeking is fast only on
        uncompressed files, on compressed files the seeking is implemented
        by reading ahead and/or restarting the decompression.

        Parameters:

            name
                file name or RarInfo instance.
            mode
                must be "r"
            pwd
                password to use for extracting.
        """

        if mode != "r":
            raise NotImplementedError("RarFile.open() supports only mode=r")

        # entry lookup
        inf = self.getinfo(name)
        if inf.is_dir():
            raise io.UnsupportedOperation("Directory does not have any data: " + inf.filename)

        # check password
        if inf.needs_password():
            pwd = pwd or self._password
            if pwd is None:
                raise PasswordRequired("File %s requires password" % inf.filename)
        else:
            pwd = None

        assert self._file_parser is not None
        return self._file_parser.open(inf, pwd)

    def read(self, name: str | Path | RarInfo, pwd: str | None = None) -> bytes:
        """Return uncompressed data for archive entry.

        For longer files using :meth:`~RarFile.open` may be better idea.

        Parameters:

            name
                filename or RarInfo instance
            pwd
                password to use for extracting.
        """

        with self.open(name, "r", pwd) as f:
            return f.read()

    def close(self) -> None:
        """Release open resources."""
        pass

    def printdir(self, file: IO[str] | None = None) -> None:
        """Print archive file list to stdout or given file.
        """
        if file is None:
            file = sys.stdout
        for f in self.infolist():
            print(f.filename, file=file)

    def extract(self, member: str | Path | RarInfo, path: str | Path | None = None,
                pwd: str | None = None) -> str | None:
        """Extract single file into current directory.

        Parameters:

            member
                filename or :class:`RarInfo` instance
            path
                optional destination path
            pwd
                optional password to use
        """
        inf = self.getinfo(member)
        return self._extract_one(inf, path, pwd, True)

    def extractall(self, path: str | Path | None = None,
                   members: Iterable[str | Path | RarInfo] | None = None,
                   pwd: str | None = None) -> None:
        """Extract all files into current directory.

        Parameters:

            path
                optional destination path
            members
                optional filename or :class:`RarInfo` instance list to extract
            pwd
                optional password to use
        """
        if members is None:
            members = self.namelist()

        done: set[str] = set()
        dirs: list[tuple[str, RarInfo]] = []
        for m in members:
            inf = self.getinfo(m)
            dst = self._extract_one(inf, path, pwd, not inf.is_dir())
            if inf.is_dir():
                assert dst is not None
                if dst not in done:
                    dirs.append((dst, inf))
                    done.add(dst)
        if dirs:
            dirs.sort(reverse=True)
            for dst, inf in dirs:
                self._set_attrs(inf, dst)

    def testrar(self, pwd: str | None = None) -> None:
        """Read all files and test CRC.
        """
        for member in self.infolist():
            if member.is_file():
                with self.open(member, 'r', pwd) as f:
                    empty_read(f, member.file_size, config.BSIZE)

    def strerror(self) -> str | None:
        """Return error string if parsing failed or None if no problems.
        """
        if not self._file_parser:
            return "Not a RAR file"
        return self._file_parser.strerror()

    ##
    ## private methods
    ##

    def _parse(self) -> None:
        """Run parser for file type
        """
        ver, sfx_ofs = _find_sfx_header(self._rarfile)
        if ver == RAR_V3:
            p3 = RAR3Parser(self._rarfile, self._password, self._crc_check,
                            self._charset, self._strict, self._info_callback,
                            sfx_ofs, self._part_only)
            self._file_parser = p3  # noqa
        elif ver == RAR_V5:
            p5 = RAR5Parser(self._rarfile, self._password, self._crc_check,
                            self._charset, self._strict, self._info_callback,
                            sfx_ofs, self._part_only)
            self._file_parser = p5  # noqa
        else:
            raise NotRarFile("Not a RAR file")

        self._file_parser.parse()
        self.comment = self._file_parser.comment

    def _extract_one(self, info: RarInfo, path: str | Path | None, pwd: str | None,
                     set_attrs: bool) -> str | None:
        fname = sanitize_filename(
            info.filename, os.path.sep, config.WIN32
        )

        if path is None:
            path = os.getcwd()
        else:
            path = os.fspath(path)
        dstfn = os.path.join(path, fname)

        # Reject members whose destination escapes `path` once symlinks
        # already created on disk are resolved.  Without this, a symlink
        # member can point outside `path` and a later file/dir member
        # named through it will be written outside the extraction root.
        real_path = os.path.realpath(path)
        real_dst = os.path.realpath(dstfn)
        if real_dst != real_path and not real_dst.startswith(real_path + os.sep):
            raise BadRarFile(
                "Refusing to extract entry that escapes destination: %r" % info.filename
            )

        dirname = os.path.dirname(dstfn)
        if dirname and dirname != ".":
            os.makedirs(dirname, exist_ok=True)

        if info.is_file():
            return self._make_file(info, dstfn, pwd, set_attrs)
        if info.is_dir():
            return self._make_dir(info, dstfn, pwd, set_attrs)
        if info.is_symlink():
            return self._make_symlink(info, dstfn, pwd, set_attrs, path)
        return None

    def _create_helper(self, name: str, flags: int, info: RarInfo) -> int:
        return os.open(name, flags)

    def _make_file(self, info: RarInfo, dstfn: str, pwd: str | None, set_attrs: bool) -> str:
        def helper(name: str, flags: int) -> int:
            return self._create_helper(name, flags, info)
        with self.open(info, "r", pwd) as src:
            with open(dstfn, "wb", opener=helper) as dst:
                shutil.copyfileobj(src, dst)
        if set_attrs:
            self._set_attrs(info, dstfn)
        return dstfn

    def _make_dir(self, info: RarInfo, dstfn: str, pwd: str | None, set_attrs: bool) -> str:
        os.makedirs(dstfn, exist_ok=True)
        if set_attrs:
            self._set_attrs(info, dstfn)
        return dstfn

    def _make_symlink(self, info: RarInfo, dstfn: str, pwd: str | None, set_attrs: bool, top: str) -> str | None:
        target_is_directory = False
        if info.host_os == RAR_OS_UNIX:
            link_name = self.read(info, pwd).decode("utf8", "replace")
            target_is_directory = (info.flags & RAR_FILE_DIRECTORY) == RAR_FILE_DIRECTORY
        elif info.file_redir:
            redir_type, _redir_flags, link_name = info.file_redir
            if redir_type == RAR5_XREDIR_WINDOWS_JUNCTION:
                warnings.warn(f"Windows junction not supported - {info.filename}", UnsupportedWarning)
                return None
            target_is_directory = (redir_type & RAR5_XREDIR_ISDIR) > 0
        else:
            warnings.warn(f"Unsupported link type - {info.filename}", UnsupportedWarning)
            return None

        # disallow abs paths
        target = os.path.normpath(link_name)
        if os.path.isabs(target) or os.path.splitdrive(target)[0]:
            raise BadSymLinkError('Absolute links not allowed')

        # disallow ../ traversal
        dest_abs = os.path.realpath(top)
        target_base = os.path.dirname(dstfn)
        target_abs = os.path.realpath(os.path.join(target_base, target))
        if os.path.commonpath([target_abs, dest_abs]) != dest_abs:
            raise BadSymLinkError('Link to outside not allowed')

        os.symlink(link_name, dstfn, target_is_directory=target_is_directory)
        return dstfn

    def _set_attrs(self, info: RarInfo, dstfn: str) -> None:
        if info.host_os == RAR_OS_UNIX:
            os.chmod(dstfn, info.mode & 0o777)
        elif info.host_os in (RAR_OS_WIN32, RAR_OS_MSDOS):
            # only keep R/O attr, except for dirs on win32
            if info.mode & DOS_MODE_READONLY and (info.is_file() or not config.WIN32):
                st = os.stat(dstfn)
                new_mode = st.st_mode & ~0o222
                os.chmod(dstfn, new_mode)

        if info.mtime:
            mtime_ns = to_nsecs(info.mtime)
            atime_ns = to_nsecs(info.atime) if info.atime else mtime_ns
            os.utime(dstfn, ns=(atime_ns, mtime_ns))
