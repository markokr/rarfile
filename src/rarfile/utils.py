"""Various low-level utitlites.
"""

import io
import os
import re
import shutil
import sys
from datetime import date, datetime, tzinfo
from pathlib import Path
from tempfile import mkstemp
from types import TracebackType
from typing import Protocol, SupportsIndex, TypeAlias, cast

from . import config

if sys.version_info < (3, 13):
    from typing_extensions import Buffer, TypeIs
else:
    from collections.abc import Buffer
    from typing import TypeIs


WritableBuffer: TypeAlias = bytearray | memoryview | Buffer


__all__ = (
    "is_filelike", "XFile", "UnicodeFilename", "nsdatetime",
    "to_nsdatetime", "to_nsecs", "to_datetime",
    "parse_dos_time", "sanitize_filename", "membuf_tempfile",
    "FileLike", "PathLike", "RawFileLike", "DateTuple",
)


PathLike: TypeAlias = str | bytes | Path
DateTuple: TypeAlias = tuple[int, int, int, int, int, int]


class FileLike(Protocol):
    def read(self, size: int = -1, /) -> bytes: ...
    def tell(self) -> int: ...
    def seek(self, ofs: int, whence: int = 0, /) -> int: ...
    def close(self) -> None: ...


class RawFileLike(Protocol):
    def read(self, size: int = -1, /) -> bytes: ...
    def tell(self) -> int: ...
    def seek(self, ofs: int, whence: int = 0, /) -> int: ...
    def close(self) -> None: ...
    def readinto(self, buf: WritableBuffer, /) -> int: ...


def is_filelike(obj: PathLike | FileLike) -> TypeIs[FileLike]:
    """Filename or file object?
    """
    if isinstance(obj, (bytes, str, Path)):
        return False
    res = True
    for a in ("read", "tell", "seek"):
        res = res and hasattr(obj, a)
    if not res:
        raise ValueError("Invalid object passed as file")
    return True


class XFile:
    """Input may be filename or file object.
    """
    __slots__ = ("_fd", "_need_close", "_initial_pos")

    _fd: FileLike
    _need_close: bool
    _initial_pos: int | None

    def __init__(self, xfile: PathLike | FileLike, bufsize: int = 1024):
        if is_filelike(xfile):
            self._fd = xfile
            self._initial_pos = self._fd.tell()
            self._need_close = False
            self._fd.seek(0)
        else:
            self._initial_pos = None
            self._need_close = True
            self._fd = open(xfile, "rb", bufsize)

    def restore_pos(self) -> None:
        if self._initial_pos is None:
            return
        try:
            self._fd.seek(self._initial_pos)
        except BaseException:
            pass

    def read(self, n: int = -1) -> bytes:
        """Read from file."""
        return self._fd.read(n)

    def tell(self) -> int:
        """Return file pos."""
        return self._fd.tell()

    def seek(self, ofs: int, whence: int = 0) -> int:
        """Move file pos."""
        return self._fd.seek(ofs, whence)

    def readinto(self, buf: WritableBuffer) -> int:
        """Read into buffer."""
        fd = cast(io.RawIOBase, self._fd)
        return fd.readinto(buf)

    def close(self) -> None:
        """Close file object."""
        if self._need_close:
            self._fd.close()

    def __enter__(self) -> "XFile":
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException |
                 None, exc_tb: TracebackType | None) -> None:
        self.close()


class UnicodeFilename:
    """Handle RAR3 unicode filename decompression.
    """

    def __init__(self, name: bytes, encdata: bytes):
        self.std_name = bytearray(name)
        self.encdata = bytearray(encdata)
        self.pos = self.encpos = 0
        self.buf = bytearray()
        self.failed = 0

    def enc_byte(self) -> int:
        """Copy encoded byte."""
        try:
            c = self.encdata[self.encpos]
            self.encpos += 1
            return c
        except IndexError:
            self.failed = 1
            return 0

    def std_byte(self) -> int:
        """Copy byte from 8-bit representation."""
        try:
            return self.std_name[self.pos]
        except IndexError:
            self.failed = 1
            return ord("?")

    def put(self, lo: int, hi: int) -> None:
        """Copy 16-bit value to result."""
        self.buf.append(lo)
        self.buf.append(hi)
        self.pos += 1

    def decode(self) -> str:
        """Decompress compressed UTF16 value."""
        hi = self.enc_byte()
        flags = flagbits = 0
        while self.encpos < len(self.encdata):
            if flagbits == 0:
                flags = self.enc_byte()
                flagbits = 8
            flagbits -= 2
            t = (flags >> flagbits) & 3
            if t == 0:
                self.put(self.enc_byte(), 0)
            elif t == 1:
                self.put(self.enc_byte(), hi)
            elif t == 2:
                self.put(self.enc_byte(), self.enc_byte())
            else:
                n = self.enc_byte()
                if n & 0x80:
                    c = self.enc_byte()
                    for _ in range((n & 0x7f) + 2):
                        lo = (self.std_byte() + c) & 0xFF
                        self.put(lo, hi)
                else:
                    for _ in range(n + 2):
                        self.put(self.std_byte(), 0)
        return self.buf.decode("utf-16le", "replace")


# pylint: disable=arguments-differ,signature-differs,redefined-outer-name
class nsdatetime(datetime):
    """Datetime that carries nanoseconds.

    Arithmetic operations will lose nanoseconds.

    .. versionadded:: 4.0
    """
    __slots__ = ("nanosecond",)
    nanosecond: int     #: Number of nanoseconds, 0 <= nanosecond <= 999999999

    def __new__(cls, year: SupportsIndex, month: SupportsIndex, day: SupportsIndex,  # type: ignore[misc]
                hour: SupportsIndex = 0, minute: SupportsIndex = 0, second: SupportsIndex = 0,
                microsecond: SupportsIndex = 0, tzinfo: tzinfo | None = None, *, fold: int = 0,
                nanosecond: SupportsIndex = 0) -> datetime:
        nsec = nanosecond.__index__()
        usec, mod = divmod(nsec, 1000) if nsec else (microsecond.__index__(), 0)
        if mod == 0:

            return datetime(year, month, day, hour, minute, second, usec, tzinfo, fold=fold)
        # pylint: disable=too-many-function-args,unexpected-keyword-arg
        self = super().__new__(cls, year, month, day, hour, minute, second, usec, tzinfo, fold=fold)
        self.nanosecond = nsec
        return self

    def isoformat(self, sep: str = "T", timespec: str = "auto") -> str:
        """Formats with nanosecond precision by default.
        """
        if timespec == "auto":
            pre, post = super().isoformat(sep, "microseconds").split(".", 1)
            return f"{pre}.{self.nanosecond:09d}{post[6:]}"
        return super().isoformat(sep, timespec)

    def astimezone(self, tz: tzinfo | None = None) -> "nsdatetime":
        """Convert to new timezone.
        """
        tmp = super().astimezone(tz)

        return self.__class__(tmp.year, tmp.month, tmp.day, tmp.hour, tmp.minute, tmp.second,  # type: ignore[return-value]
                              nanosecond=self.nanosecond, tzinfo=tmp.tzinfo, fold=tmp.fold)

    def replace(self,
                year: SupportsIndex | None = None,
                month: SupportsIndex | None = None,
                day: SupportsIndex | None = None,
                hour: SupportsIndex | None = None,
                minute: SupportsIndex | None = None,
                second: SupportsIndex | None = None,
                microsecond: SupportsIndex | None = None,
                tzinfo: tzinfo | None = None,
                *,
                fold: int | None = None,
                nanosecond: SupportsIndex | None = None) -> "nsdatetime":
        """Return new timestamp with specified fields replaced.
        """
        return self.__class__(  # type: ignore[return-value]
            self.year if year is None else year,
            self.month if month is None else month,
            self.day if day is None else day,
            self.hour if hour is None else hour,
            self.minute if minute is None else minute,
            self.second if second is None else second,
            nanosecond=((self.nanosecond if microsecond is None else microsecond.__index__() * 1000)
                        if nanosecond is None else nanosecond),
            tzinfo=self.tzinfo if tzinfo is None else tzinfo,
            fold=self.fold if fold is None else fold)

    def __hash__(self) -> int:
        return hash((super().__hash__(), self.nanosecond)) if self.nanosecond else super().__hash__()

    def __eq__(self, other: object) -> bool:
        if not super().__eq__(other):
            return False
        if isinstance(other, nsdatetime):
            nanosecond = other.nanosecond
        elif isinstance(other, datetime):
            nanosecond = other.microsecond * 1000
        else:
            nanosecond = 0
        return self.nanosecond == nanosecond

    def __gt__(self, other: date) -> bool:
        xother = cast(datetime, other)
        if super().__gt__(xother):
            return True
        if not super().__eq__(xother):
            return False
        if isinstance(xother, nsdatetime):
            nanosecond = xother.nanosecond
        elif isinstance(xother, datetime):
            nanosecond = xother.microsecond * 1000
        else:
            nanosecond = 0
        return self.nanosecond > nanosecond

    def __lt__(self, other: date) -> bool:
        return not (self > other or self == other)

    def __ge__(self, other: date) -> bool:
        return not self < other

    def __le__(self, other: date) -> bool:
        return not self > other

    def __ne__(self, other: object) -> bool:
        return not self == other


def to_nsdatetime(dt: datetime, nsec: int) -> datetime:
    """Apply nanoseconds to datetime.
    """
    if not nsec:
        return dt
    return nsdatetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second,
                      tzinfo=dt.tzinfo, fold=dt.fold, nanosecond=nsec)


def to_nsecs(dt: datetime) -> int:
    """Convert datatime instance to nanoseconds.
    """
    secs = int(dt.timestamp())
    nsecs = dt.nanosecond if isinstance(dt, nsdatetime) else dt.microsecond * 1000
    return secs * 1000000000 + nsecs


def to_datetime(t: DateTuple) -> datetime:
    """Convert 6-part time tuple into datetime object.
    """
    # extract values
    year, mon, day, h, m, s = t

    # assume the values are valid
    try:
        return datetime(year, mon, day, h, m, s)
    except ValueError:
        pass

    # sanitize invalid values
    mday = (0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    mon = max(1, min(mon, 12))
    day = max(1, min(day, mday[mon]))
    h = min(h, 23)
    m = min(m, 59)
    s = min(s, 59)
    return datetime(year, mon, day, h, m, s)


def parse_dos_time(stamp: int) -> DateTuple:
    """Parse standard 32-bit DOS timestamp.
    """
    sec, stamp = stamp & 0x1F, stamp >> 5
    mn, stamp = stamp & 0x3F, stamp >> 6
    hr, stamp = stamp & 0x1F, stamp >> 5
    day, stamp = stamp & 0x1F, stamp >> 5
    mon, stamp = stamp & 0x0F, stamp >> 4
    yr = (stamp & 0x7F) + 1980
    return (yr, mon, day, hr, mn, sec * 2)


_BAD_CHARS = r"""\x00-\x1F<>|"?*"""
RC_BAD_CHARS_UNIX = re.compile(r"[%s]" % _BAD_CHARS)
RC_BAD_CHARS_WIN32 = re.compile(r"[%s:^\\]" % _BAD_CHARS)


def sanitize_filename(fname: str, pathsep: str, is_win32: bool) -> str:
    """Make filename safe for write access.
    """
    if is_win32:
        if len(fname) > 1 and fname[1] == ":":
            fname = fname[2:]
        rc = RC_BAD_CHARS_WIN32
    else:
        rc = RC_BAD_CHARS_UNIX
    if rc.search(fname):
        fname = rc.sub("_", fname)

    parts: list[str] = []
    for seg in fname.split("/"):
        if seg in ("", ".", ".."):
            continue
        if is_win32 and seg[-1] in (" ", "."):
            seg = seg[:-1] + "_"
        parts.append(seg)
    return pathsep.join(parts)


def membuf_tempfile(memfile: FileLike) -> str:
    """Write in-memory file object to real file.
    """
    memfile.seek(0, 0)

    tmpfd, tmpname = mkstemp(suffix=".rar", dir=config.HACK_TMP_DIR)
    tmpf = os.fdopen(tmpfd, "wb")

    try:
        shutil.copyfileobj(memfile, tmpf, config.BSIZE)
        tmpf.close()
    except BaseException:
        tmpf.close()
        os.unlink(tmpname)
        raise
    return tmpname
