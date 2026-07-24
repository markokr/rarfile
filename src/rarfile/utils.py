"""Various low-level utitlites.
"""

from datetime import datetime
from pathlib import Path


__all__ = ("is_filelike", "XFile", "UnicodeFilename", "nsdatetime", "to_nsdatetime", "to_nsecs")


def is_filelike(obj):
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

    def __init__(self, xfile, bufsize=1024):
        if is_filelike(xfile):
            self._initial_pos = xfile.tell()
            self._need_close = False
            self._fd = xfile
            self._fd.seek(0)
        else:
            self._initial_pos = None
            self._need_close = True
            self._fd = open(xfile, "rb", bufsize)

    def restore_pos(self):
        if self._initial_pos is None:
            return
        try:
            self._fd.seek(self._initial_pos)
        except:
            pass

    def read(self, n=None):
        """Read from file."""
        return self._fd.read(n)

    def tell(self):
        """Return file pos."""
        return self._fd.tell()

    def seek(self, ofs, whence=0):
        """Move file pos."""
        return self._fd.seek(ofs, whence)

    def readinto(self, buf):
        """Read into buffer."""
        return self._fd.readinto(buf)

    def close(self):
        """Close file object."""
        if self._need_close:
            self._fd.close()

    def __enter__(self):
        return self

    def __exit__(self, typ, val, tb):
        self.close()


class UnicodeFilename:
    """Handle RAR3 unicode filename decompression.
    """
    def __init__(self, name, encdata):
        self.std_name = bytearray(name)
        self.encdata = bytearray(encdata)
        self.pos = self.encpos = 0
        self.buf = bytearray()
        self.failed = 0

    def enc_byte(self):
        """Copy encoded byte."""
        try:
            c = self.encdata[self.encpos]
            self.encpos += 1
            return c
        except IndexError:
            self.failed = 1
            return 0

    def std_byte(self):
        """Copy byte from 8-bit representation."""
        try:
            return self.std_name[self.pos]
        except IndexError:
            self.failed = 1
            return ord("?")

    def put(self, lo, hi):
        """Copy 16-bit value to result."""
        self.buf.append(lo)
        self.buf.append(hi)
        self.pos += 1

    def decode(self):
        """Decompress compressed UTF16 value."""
        hi = self.enc_byte()
        flagbits = 0
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


# pylint: disable=arguments-differ,signature-differs
class nsdatetime(datetime):
    """Datetime that carries nanoseconds.

    Arithmetic operations will lose nanoseconds.

    .. versionadded:: 4.0
    """
    __slots__ = ("nanosecond",)
    nanosecond: int     #: Number of nanoseconds, 0 <= nanosecond <= 999999999

    def __new__(cls, year, month=None, day=None, hour=0, minute=0, second=0,
                microsecond=0, tzinfo=None, *, fold=0, nanosecond=0):
        usec, mod = divmod(nanosecond, 1000) if nanosecond else (microsecond, 0)
        if mod == 0:
            return datetime(year, month, day, hour, minute, second, usec, tzinfo, fold=fold)
        self = super().__new__(cls, year, month, day, hour, minute, second, usec, tzinfo, fold=fold)
        self.nanosecond = nanosecond
        return self

    def isoformat(self, sep="T", timespec="auto"):
        """Formats with nanosecond precision by default.
        """
        if timespec == "auto":
            pre, post = super().isoformat(sep, "microseconds").split(".", 1)
            return f"{pre}.{self.nanosecond:09d}{post[6:]}"
        return super().isoformat(sep, timespec)

    def astimezone(self, tz=None):
        """Convert to new timezone.
        """
        tmp = super().astimezone(tz)
        return self.__class__(tmp.year, tmp.month, tmp.day, tmp.hour, tmp.minute, tmp.second,
                              nanosecond=self.nanosecond, tzinfo=tmp.tzinfo, fold=tmp.fold)

    def replace(self, year=None, month=None, day=None, hour=None, minute=None, second=None,
                microsecond=None, tzinfo=None, *, fold=None, nanosecond=None):
        """Return new timestamp with specified fields replaced.
        """
        return self.__class__(
            self.year if year is None else year,
            self.month if month is None else month,
            self.day if day is None else day,
            self.hour if hour is None else hour,
            self.minute if minute is None else minute,
            self.second if second is None else second,
            nanosecond=((self.nanosecond if microsecond is None else microsecond * 1000)
                        if nanosecond is None else nanosecond),
            tzinfo=self.tzinfo if tzinfo is None else tzinfo,
            fold=self.fold if fold is None else fold)

    def __hash__(self):
        return hash((super().__hash__(), self.nanosecond)) if self.nanosecond else super().__hash__()

    def __eq__(self, other):
        return super().__eq__(other) and self.nanosecond == (
            other.nanosecond if isinstance(other, nsdatetime) else other.microsecond * 1000)

    def __gt__(self, other):
        return super().__gt__(other) or (super().__eq__(other) and self.nanosecond > (
            other.nanosecond if isinstance(other, nsdatetime) else other.microsecond * 1000))

    def __lt__(self, other):
        return not (self > other or self == other)

    def __ge__(self, other):
        return not self < other

    def __le__(self, other):
        return not self > other

    def __ne__(self, other):
        return not self == other


def to_nsdatetime(dt, nsec):
    """Apply nanoseconds to datetime.
    """
    if not nsec:
        return dt
    return nsdatetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second,
                      tzinfo=dt.tzinfo, fold=dt.fold, nanosecond=nsec)


def to_nsecs(dt):
    """Convert datatime instance to nanoseconds.
    """
    secs = int(dt.timestamp())
    nsecs = dt.nanosecond if isinstance(dt, nsdatetime) else dt.microsecond * 1000
    return secs * 1000000000 + nsecs
