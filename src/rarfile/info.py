"""RAR entry records.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import TypeAlias

from .bits import (
    RAR5_BLOCK_ENCRYPTION, RAR5_BLOCK_FLAG_SPLIT_AFTER,
    RAR5_BLOCK_FLAG_SPLIT_BEFORE, RAR5_COMPR_SOLID, RAR5_FILE_FLAG_ISDIR,
    RAR5_MAIN_FLAG_SOLID, RAR5_XREDIR_UNIX_SYMLINK,
    RAR5_XREDIR_WINDOWS_JUNCTION, RAR5_XREDIR_WINDOWS_SYMLINK,
    RAR_BLOCK_ENDARC, RAR_BLOCK_FILE, RAR_BLOCK_MAIN, RAR_BLOCK_MARK,
    RAR_BLOCK_SUB, RAR_FILE_DIRECTORY, RAR_FILE_PASSWORD, RAR_FILE_SPLIT_AFTER,
    RAR_FILE_SPLIT_BEFORE, RAR_MAIN_PASSWORD, RAR_MAIN_SOLID, RAR_OS_UNIX,
)
from .crypto import HashContext
from .utils import DateTuple, FileLike, PathLike

__all__ = (
    "RarEntry", "RarInfo",
    "Rar3Info", "Rar3SubInfo", "Rar3MainInfo", "Rar3EndArcInfo",
    "Rar3GenericInfo",
    "Rar5BaseFile", "Rar5FileInfo", "Rar5ServiceInfo",
    "Rar5MainInfo", "Rar5EncryptionInfo", "Rar5EndArcInfo",
)


FileEncryption: TypeAlias = tuple[int, int, int, bytes, bytes, bytes | None]


@dataclass(kw_only=True, eq=False)
class RarEntry:
    """Base class for all records in a rar archive.

    .. versionadded:: 5.0

    Attributes:

        type
            RAR3 block type.  One of RAR_BLOCK_* constants.  RAR5 blocks are mappend

        flags
            File modification timestamp.   As tuple of (year, month, day, hour, minute, second).
            RAR5 allows archives where it is missing, it's None then.

        block_type
            RAR5 block type.  One of RAR5_BLOCK_* contants.  None on RAR3.

    """

    type: int = 0
    flags: int
    volume: int = 0
    volume_file: PathLike | FileLike | None = None

    header_crc: int
    header_size: int
    header_offset: int
    data_offset: int
    add_size: int

    # rar5 low-level framing, None for rar3
    block_type: int | None = None
    block_flags: int | None = None
    block_extra_size: int = 0

    def needs_password(self) -> bool:
        """Returns True if data is stored password-protected.
        """
        if self.type == RAR_BLOCK_FILE:
            return (self.flags & RAR_FILE_PASSWORD) > 0
        return False

    def _must_disable_hack(self) -> bool:
        """Returns True if temp-file extraction hack must be avoided."""
        return False


@dataclass(kw_only=True, eq=False)
class RarInfo(RarEntry):
    r"""A file entry in rar archive.

    Timestamps as :class:`~datetime.datetime` are without timezone in RAR3,
    with UTC timezone in RAR5 archives.

    Attributes:

        filename
            File name with relative path.
            Path separator is "/".  Always unicode string.

        date_time
            File modification timestamp.   As tuple of (year, month, day, hour, minute, second).
            RAR5 allows archives where it is missing, it's None then.

        comment
            Optional file comment field.  Unicode string.  (RAR3-only)

        file_size
            Uncompressed size.

        compress_size
            Compressed size.

        compress_type
            Compression method: one of :data:`RAR_M0` .. :data:`RAR_M5` constants.

        extract_version
            Minimal Rar version needed for decompressing.  As (major*10 + minor),
            so 2.9 is 29.

            RAR3: 10, 20, 29

            RAR5 does not have such field in archive, it's simply set to 50.

        host_os
            Host OS type, one of RAR_OS_* constants.

            RAR3: :data:`RAR_OS_WIN32`, :data:`RAR_OS_UNIX`, :data:`RAR_OS_MSDOS`,
            :data:`RAR_OS_OS2`, :data:`RAR_OS_BEOS`.

            RAR5: :data:`RAR_OS_WIN32`, :data:`RAR_OS_UNIX`.

        mode
            File attributes. May be either dos-style or unix-style, depending on host_os.

        mtime
            File modification time.  Same value as :attr:`date_time`
            but as :class:`~datetime.datetime` object with extended precision.

        ctime
            Optional time field: creation time.  As :class:`~datetime.datetime` object.

        atime
            Optional time field: last access time.  As :class:`~datetime.datetime` object.

        arctime
            Optional time field: archival time.  As :class:`~datetime.datetime` object.
            (RAR3-only)

        CRC
            CRC-32 of uncompressed file, unsigned int.

            RAR5: may be None.

        blake2sp_hash
            Blake2SP hash over decompressed data.  (RAR5-only)

        volume
            Volume nr, starting from 0.

        volume_file
            Volume file name, where file starts.

        file_redir
            If not None, file is link of some sort.  Contains tuple of (type, flags, target).
            (RAR5-only)

            Type is one of constants:

                :data:`RAR5_XREDIR_UNIX_SYMLINK`
                    Unix symlink.
                :data:`RAR5_XREDIR_WINDOWS_SYMLINK`
                    Windows symlink.
                :data:`RAR5_XREDIR_WINDOWS_JUNCTION`
                    Windows junction.
                :data:`RAR5_XREDIR_HARD_LINK`
                    Hard link to target.
                :data:`RAR5_XREDIR_FILE_COPY`
                    Current file is copy of another archive entry.

            Flags may contain bits:

                :data:`RAR5_XREDIR_ISDIR`
                    Symlink points to directory.
    """

    # zipfile-compatible fields
    filename: str
    orig_filename: bytes
    file_size: int
    compress_size: int | None = None
    date_time: DateTuple | None = None
    CRC: int | None = None

    # optional extended time fields, datetime() objects.
    mtime: datetime | None = None
    ctime: datetime | None = None
    atime: datetime | None = None
    arctime: datetime | None = None

    extract_version: int
    mode: int
    host_os: int
    compress_type: int

    # rar3-only field
    comment: str | None = None

    # rar5-only fields
    blake2sp_hash: bytes | None = None
    file_redir: tuple[int, int, str] | None = None
    file_version: tuple[int, int] | None = None
    file_owner: tuple[bytes | None, bytes | None, int | None, int | None] | None = None

    # internal hashing fields
    _md_class: type[HashContext] | None = None
    _md_expect: int | bytes | None = None

    # zipfile compat
    def is_dir(self) -> bool:
        """Returns True if entry is a directory.

        .. versionadded:: 4.0
        """
        return False

    def is_symlink(self) -> bool:
        """Returns True if entry is a symlink.

        .. versionadded:: 4.0
        """
        return False

    def is_file(self) -> bool:
        """Returns True if entry is a normal file.

        .. versionadded:: 4.0
        """
        return False

    def isdir(self) -> bool:
        """Returns True if entry is a directory.

        .. deprecated:: 4.0
        """
        return self.is_dir()

#
# RAR3 format
#


@dataclass(kw_only=True, eq=False)
class Rar3Info(RarInfo):
    """RAR3 file record."""

    type: int = RAR_BLOCK_FILE
    _name_size: int
    salt: bytes | None

    def _must_disable_hack(self) -> bool:
        if self.type == RAR_BLOCK_FILE:
            if self.flags & RAR_FILE_PASSWORD:
                return True
            elif self.flags & (RAR_FILE_SPLIT_BEFORE | RAR_FILE_SPLIT_AFTER):
                return True
        return False

    def is_dir(self) -> bool:
        """Returns True if entry is a directory."""
        if self.type == RAR_BLOCK_FILE and not self.is_symlink():
            return (self.flags & RAR_FILE_DIRECTORY) == RAR_FILE_DIRECTORY
        return False

    def is_symlink(self) -> bool:
        """Returns True if entry is a symlink."""
        return (
            self.type == RAR_BLOCK_FILE and
            self.host_os == RAR_OS_UNIX and
            self.mode & 0xF000 == 0xA000
        )

    def is_file(self) -> bool:
        """Returns True if entry is a normal file."""
        return (
            self.type == RAR_BLOCK_FILE and
            not (self.is_dir() or self.is_symlink())
        )


@dataclass(kw_only=True, eq=False)
class Rar3SubInfo(Rar3Info):
    """RAR3 service subblock, using the file-record layout."""

    type: int = RAR_BLOCK_SUB


@dataclass(kw_only=True, eq=False)
class Rar3MainInfo(RarEntry):
    """RAR3 archive main record."""

    type: int = RAR_BLOCK_MAIN
    comment: str | None

    def _must_disable_hack(self) -> bool:
        if self.flags & (RAR_MAIN_SOLID | RAR_MAIN_PASSWORD):
            return True
        return False


@dataclass(kw_only=True, eq=False)
class Rar3EndArcInfo(RarEntry):
    """RAR3 end of archive record."""

    type: int = RAR_BLOCK_ENDARC
    endarc_datacrc: int | None
    endarc_volnr: int | None


@dataclass(kw_only=True, eq=False)
class Rar3GenericInfo(RarEntry):
    """RAR3 mark and old-style subblocks without dedicated fields."""

    type: int = RAR_BLOCK_MARK
    old_sub_type: int | None = None


#
# RAR5 format
#

@dataclass(kw_only=True, eq=False)
class Rar5MainInfo(RarEntry):
    """RAR5 archive main record."""

    type: int = RAR_BLOCK_MAIN
    main_flags: int
    main_volume_number: int | None

    def _must_disable_hack(self) -> bool:
        if self.main_flags & RAR5_MAIN_FLAG_SOLID:
            return True
        return False


@dataclass(kw_only=True, eq=False)
class Rar5EncryptionInfo(RarEntry):
    """RAR5 archive header encryption record."""

    type: int = RAR5_BLOCK_ENCRYPTION
    encryption_algo: int
    encryption_flags: int
    encryption_kdf_count: int
    encryption_salt: bytes
    encryption_check_value: bytes | None

    def needs_password(self) -> bool:
        return True


@dataclass(kw_only=True, eq=False)
class Rar5EndArcInfo(RarEntry):
    """RAR5 end of archive record."""

    type: int = RAR_BLOCK_ENDARC
    endarc_flags: int


@dataclass(kw_only=True, eq=False)
class Rar5BaseFile(RarInfo):
    """Shared struct for RAR5 file & service records."""

    file_flags: int
    file_compress_flags: int
    file_host_os: int
    file_encryption: FileEncryption

    def _must_disable_hack(self) -> bool:
        if self.flags & RAR_FILE_PASSWORD:
            return True
        if self.block_flags is not None and self.block_flags & (
                RAR5_BLOCK_FLAG_SPLIT_BEFORE | RAR5_BLOCK_FLAG_SPLIT_AFTER):
            return True
        if self.file_compress_flags & RAR5_COMPR_SOLID:
            return True
        if self.file_redir:
            return True
        return False


@dataclass(kw_only=True, eq=False)
class Rar5FileInfo(Rar5BaseFile):
    """RAR5 file record."""

    type: int = RAR_BLOCK_FILE

    def is_symlink(self) -> bool:
        """Returns True if entry is a symlink."""
        return (
            self.file_redir is not None and
            self.file_redir[0] in (
                RAR5_XREDIR_UNIX_SYMLINK,
                RAR5_XREDIR_WINDOWS_SYMLINK,
                RAR5_XREDIR_WINDOWS_JUNCTION,
            )
        )

    def is_file(self) -> bool:
        """Returns True if entry is a normal file."""
        return not (self.is_dir() or self.is_symlink())

    def is_dir(self) -> bool:
        """Returns True if entry is a directory."""
        if not self.file_redir and self.file_flags & RAR5_FILE_FLAG_ISDIR:
            return True
        return False


@dataclass(kw_only=True, eq=False)
class Rar5ServiceInfo(Rar5BaseFile):
    """RAR5 service record."""

    type: int = RAR_BLOCK_SUB
