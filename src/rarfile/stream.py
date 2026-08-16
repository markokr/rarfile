"""File-like objests for reading data.
"""

import io
import os
from collections.abc import Sequence
from subprocess import Popen
from typing import TYPE_CHECKING, cast

from . import config
from .backend import check_returncode, custom_popen, empty_read, tool_setup
from .bits import RAR_BLOCK_MAIN, RAR_BLOCK_MARK, RAR_FILE_SPLIT_AFTER
from .crypto import HashContext, NoHashContext
from .errors import BadRarFile
from .info import RarInfo
from .utils import PathLike, RawFileLike, WritableBuffer, XFile

if TYPE_CHECKING:
    from .format import CommonParser

__all__ = ("RarExtFile", "DirectReader", "PipeReader", "BytesReader")


class RarExtFile(io.RawIOBase):
    """Base class for file-like object that :meth:`RarFile.open` returns.

    Provides public methods and common crc checking.

    Behaviour:
     - no short reads - .read() and .readinfo() read as much as requested.
     - no internal buffer, use io.BufferedReader for that.
    """
    name: str | None = None     #: Filename of the archive entry
    mode: str = "rb"
    _inf: RarInfo
    _fd: RawFileLike | None = None
    _remain: int = 0
    _returncode: int = 0
    _md_context: HashContext | None = None
    _seeking: bool = False

    def __init__(self, inf: RarInfo):
        super().__init__()
        self._inf = inf
        self.name = inf.filename

    def _open_extfile(self) -> None:
        if self._fd:
            self._fd.close()
        md_class: type[HashContext]
        if self._seeking:
            md_class = NoHashContext
        else:
            md_class = self._inf._md_class or NoHashContext
        self._md_context = md_class()
        self._fd = None
        self._remain = self._inf.file_size

    def read(self, n: int | None = -1) -> bytes:
        """Read all or specified amount of data from archive entry."""

        # sanitize count
        if n is None or n < 0:
            n = self._remain
        elif n > self._remain:
            n = self._remain
        if n == 0:
            return b""

        assert self._md_context is not None
        buf: list[bytes] = []
        orig = n
        while n > 0:
            # actual read
            data = self._read(n)
            if not data:
                break
            buf.append(data)
            self._md_context.update(data)
            self._remain -= len(data)
            n -= len(data)
        data = b"".join(buf)
        if n > 0:
            if self._returncode:
                check_returncode(self._returncode, "", tool_setup().get_errmap())
            raise BadRarFile("Failed the read enough data: req=%d got=%d" % (orig, len(data)))

        # done?
        if not data or self._remain == 0:
            # self.close()
            self._check()
        return data

    def _check(self) -> None:
        """Check final CRC."""
        assert self._md_context is not None and self._inf is not None
        final = self._md_context.digest()
        exp = self._inf._md_expect
        if exp is None:
            return
        if final is None:
            return
        if self._returncode:
            check_returncode(self._returncode, "", tool_setup().get_errmap())
        if self._remain != 0:
            raise BadRarFile("Failed the read enough data")
        if final != exp:
            raise BadRarFile("Corrupt file - CRC check failed: %s - exp=%r got=%r" % (
                self._inf.filename, exp, final))

    def _read(self, cnt: int) -> bytes:
        """Actual read that gets sanitized cnt."""
        raise NotImplementedError("_read")

    def close(self) -> None:
        """Close open resources."""

        super().close()

        if self._fd:
            self._fd.close()
            self._fd = None

    def __del__(self) -> None:
        """Hook delete to make sure tempfile is removed."""
        self.close()

    def readinto(self, buf: WritableBuffer) -> int:
        """Zero-copy read directly into buffer.

        Returns bytes read.
        """
        raise NotImplementedError("readinto")

    def tell(self) -> int:
        """Return current reading position in uncompressed data."""
        assert self._inf is not None
        return self._inf.file_size - self._remain

    def seek(self, offset: int, whence: int = 0) -> int:
        """Seek in data.

        On uncompressed files, the seeking works by actual
        seeks so it's fast.  On compressed files its slow
        - forward seeking happens by reading ahead,
        backwards by re-opening and decompressing from the start.
        """

        # disable crc check when seeking
        if not self._seeking:
            self._md_context = NoHashContext()
            self._seeking = True

        assert self._inf is not None
        fsize = self._inf.file_size
        cur_ofs = self.tell()

        if whence == 0:     # seek from beginning of file
            new_ofs = offset
        elif whence == 1:   # seek from current position
            new_ofs = cur_ofs + offset
        elif whence == 2:   # seek from end of file
            new_ofs = fsize + offset
        else:
            raise ValueError("Invalid value for whence")

        # sanity check
        if new_ofs < 0:
            new_ofs = 0
        elif new_ofs > fsize:
            new_ofs = fsize

        # do the actual seek
        if new_ofs >= cur_ofs:
            self._skip(new_ofs - cur_ofs)
        else:
            self._open_extfile()
            self._skip(new_ofs)
        return self.tell()

    def _skip(self, cnt: int) -> None:
        """Read and discard data"""
        empty_read(self, cnt, config.BSIZE)

    def readable(self) -> bool:
        """Returns True"""
        return True

    def writable(self) -> bool:
        """Returns False.

        Writing is not supported.
        """
        return False

    def seekable(self) -> bool:
        """Returns True.

        Seeking is supported, although it's slow on compressed files.
        """
        return True

    def readall(self) -> bytes:
        """Read all remaining data"""
        # avoid RawIOBase default impl
        return self.read()


class PipeReader(RarExtFile):
    """Read data from pipe, handle tempfile cleanup."""

    _proc: Popen[bytes] | None = None

    def __init__(self, inf: RarInfo, cmd: Sequence[str], tempfile: str | None = None):
        super().__init__(inf)
        self._cmd = cmd
        self._proc = None
        self._tempfile = tempfile
        self._open_extfile()

    def _close_proc(self) -> None:
        if not self._proc:
            return
        for f in (self._proc.stdout, self._proc.stderr, self._proc.stdin):
            if f:
                f.close()
        self._proc.wait()
        assert self._proc.returncode is not None
        self._returncode = self._proc.returncode
        self._proc = None

    def _open_extfile(self) -> None:
        super()._open_extfile()

        # stop old process
        self._close_proc()

        # launch new process
        self._returncode = 0
        self._proc = custom_popen(self._cmd)
        self._fd = cast("RawFileLike | None", self._proc.stdout)
        #self._fd = self._proc.stdout

    def _read(self, cnt: int) -> bytes:
        """Read from pipe."""

        assert self._fd is not None
        # normal read is usually enough
        data = self._fd.read(cnt)
        if len(data) == cnt or not data:
            return data

        # short read, try looping
        buf = [data]
        cnt -= len(data)
        while cnt > 0:
            data = self._fd.read(cnt)
            if not data:
                break
            cnt -= len(data)
            buf.append(data)
        return b"".join(buf)

    def close(self) -> None:
        """Close open resources."""

        self._close_proc()
        super().close()

        if self._tempfile:
            try:
                os.unlink(self._tempfile)
            except OSError:
                pass
            self._tempfile = None

    def readinto(self, buf: WritableBuffer) -> int:
        """Zero-copy read directly into buffer."""
        vbuf = memoryview(buf)
        cnt = len(vbuf)
        if cnt > self._remain:
            cnt = self._remain
        assert self._fd is not None and self._md_context is not None
        res = got = 0
        while got < cnt:
            res = self._fd.readinto(vbuf[got: cnt])
            if not res:
                break
            self._md_context.update(vbuf[got: got + res])
            self._remain -= res
            got += res
        return got


class DirectReader(RarExtFile):
    """Read uncompressed data directly from archive.
    """
    _cur: RarInfo | None = None
    _cur_avail: int | None = None
    _volfile: PathLike | None = None
    _parser: "CommonParser"

    def __init__(self, parser: "CommonParser", inf: RarInfo):
        super().__init__(inf)
        self._parser = parser

        self._open_extfile()

    def _open_extfile(self) -> None:
        super()._open_extfile()

        assert self._inf.volume_file is not None
        assert self._inf.header_offset is not None
        self._volfile = cast(PathLike, self._inf.volume_file)
        self._fd = XFile(self._volfile, 0)
        self._fd.seek(self._inf.header_offset, 0)
        cur = self._parser._parse_header(self._fd)
        assert isinstance(cur, RarInfo)
        self._cur = cur
        self._cur_avail = cur.add_size

    def _skip(self, cnt: int) -> None:
        """RAR Seek, skipping through rar files to get to correct position
        """
        assert self._fd is not None and self._cur_avail is not None

        while cnt > 0:
            # next vol needed?
            if self._cur_avail == 0:
                if not self._open_next():
                    break

            # fd is in read pos, do the read
            if cnt > self._cur_avail:
                cnt -= self._cur_avail
                self._remain -= self._cur_avail
                self._cur_avail = 0
            else:
                self._fd.seek(cnt, 1)
                self._cur_avail -= cnt
                self._remain -= cnt
                cnt = 0

    def _read(self, cnt: int) -> bytes:
        """Read from potentially multi-volume archive."""

        assert self._fd is not None and self._cur is not None and self._cur_avail is not None
        pos = self._fd.tell()
        need = self._cur.data_offset + self._cur.add_size - self._cur_avail
        if pos != need:
            self._fd.seek(need, 0)

        buf: list[bytes] = []
        while cnt > 0:
            # next vol needed?
            if self._cur_avail == 0:
                if not self._open_next():
                    break

            # fd is in read pos, do the read
            if cnt > self._cur_avail:
                data = self._fd.read(self._cur_avail)
            else:
                data = self._fd.read(cnt)
            if not data:
                break

            # got some data
            cnt -= len(data)
            self._cur_avail -= len(data)
            buf.append(data)

        if len(buf) == 1:
            return buf[0]
        return b"".join(buf)

    def _open_next(self) -> bool:
        """Proceed to next volume."""

        assert self._cur is not None and self._parser is not None and self._inf is not None
        # is the file split over archives?
        if (self._cur.flags & RAR_FILE_SPLIT_AFTER) == 0:
            return False

        if self._fd:
            self._fd.close()
            self._fd = None

        # open next part
        assert self._volfile is not None
        self._volfile = self._parser._next_volname(self._volfile)
        fd = open(self._volfile, "rb", 0)
        self._fd = fd
        sig = fd.read(len(self._parser._expect_sig))
        if sig != self._parser._expect_sig:
            raise BadRarFile("Invalid signature")

        # loop until first file header
        while True:
            cur = self._parser._parse_header(fd)
            if not cur:
                raise BadRarFile("Unexpected EOF")
            if cur.type in (RAR_BLOCK_MARK, RAR_BLOCK_MAIN):
                if cur.add_size:
                    fd.seek(cur.add_size, 1)
                continue
            assert isinstance(cur, RarInfo)
            if cur.orig_filename != self._inf.orig_filename:
                raise BadRarFile("Did not found file entry")
            self._cur = cur
            self._cur_avail = cur.add_size
            return True

    def readinto(self, buf: WritableBuffer) -> int:
        """Zero-copy read directly into buffer."""
        assert self._fd is not None and self._cur_avail is not None and self._md_context is not None
        got = 0
        vbuf = memoryview(buf)
        while got < len(vbuf):
            # next vol needed?
            if self._cur_avail == 0:
                if not self._open_next():
                    break

            # length for next read
            cnt = len(vbuf) - got
            if cnt > self._cur_avail:
                cnt = self._cur_avail

            # read into temp view
            res = self._fd.readinto(vbuf[got: got + cnt])
            if not res:
                break
            self._md_context.update(vbuf[got: got + res])
            self._cur_avail -= res
            self._remain -= res
            got += res
        return got


class BytesReader(RarExtFile):
    """Read uncompressed data directly from archive.
    """

    def __init__(self, data: bytes, inf: RarInfo):
        super().__init__(inf)

        self.name = inf.filename
        self._fd = io.BytesIO(data)

    def seek(self, offset: int, whence: int = 0) -> int:
        if self._fd is None:
            return 0
        return self._fd.seek(offset, whence)

    def tell(self) -> int:
        if self._fd is None:
            return 0
        return self._fd.tell()

    def read(self, n: int | None = -1) -> bytes:
        cnt = n if n is not None else -1
        return self._read(cnt)

    def readinto(self, buf: WritableBuffer) -> int:
        if self._fd is None:
            return 0
        return self._fd.readinto(buf)

    def _read(self, cnt: int) -> bytes:
        """Actual read that gets sanitized cnt."""
        if self._fd is None:
            return b""
        return self._fd.read(cnt)
