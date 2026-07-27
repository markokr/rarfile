"""RAR file format parser.
"""

from .bits import (
    RAR5_BLOCK_ENCRYPTION, RAR5_BLOCK_FLAG_SPLIT_AFTER,
    RAR5_BLOCK_FLAG_SPLIT_BEFORE, RAR5_COMPR_SOLID, RAR5_FILE_FLAG_ISDIR,
    RAR5_MAIN_FLAG_SOLID, RAR5_XREDIR_UNIX_SYMLINK,
    RAR5_XREDIR_WINDOWS_JUNCTION, RAR5_XREDIR_WINDOWS_SYMLINK,
    RAR_BLOCK_ENDARC, RAR_BLOCK_FILE, RAR_BLOCK_MAIN, RAR_BLOCK_SUB,
    RAR_FILE_DIRECTORY, RAR_FILE_PASSWORD, RAR_FILE_SPLIT_AFTER,
    RAR_FILE_SPLIT_BEFORE, RAR_MAIN_PASSWORD, RAR_MAIN_SOLID, RAR_OS_UNIX,
)

__all__ = ("RarInfo", "Rar3Info", "Rar5Info", "Rar5BaseFile",
           "Rar5FileInfo", "Rar5ServiceInfo", "Rar5MainInfo",
           "Rar5EncryptionInfo", "Rar5EndArcInfo")


class RarInfo:
    r"""An entry in rar archive.

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
    filename = None
    file_size = None
    compress_size = None
    date_time = None
    CRC = None
    volume = None
    orig_filename = None

    # optional extended time fields, datetime() objects.
    mtime = None
    ctime = None
    atime = None

    extract_version = None
    mode = None
    host_os = None
    compress_type = None

    # rar3-only fields
    comment = None
    arctime = None

    # rar5-only fields
    blake2sp_hash = None
    file_redir = None

    # internal fields
    flags = 0
    type = None

    # zipfile compat
    def is_dir(self):
        """Returns True if entry is a directory.

        .. versionadded:: 4.0
        """
        return False

    def is_symlink(self):
        """Returns True if entry is a symlink.

        .. versionadded:: 4.0
        """
        return False

    def is_file(self):
        """Returns True if entry is a normal file.

        .. versionadded:: 4.0
        """
        return False

    def needs_password(self):
        """Returns True if data is stored password-protected.
        """
        if self.type == RAR_BLOCK_FILE:
            return (self.flags & RAR_FILE_PASSWORD) > 0
        return False

    def isdir(self):
        """Returns True if entry is a directory.

        .. deprecated:: 4.0
        """
        return self.is_dir()


class Rar3Info(RarInfo):
    """RAR3 specific fields."""
    extract_version = 15
    salt = None
    add_size = 0
    header_crc = None
    header_size = None
    header_offset = None
    data_offset = None
    _md_class = None
    _md_expect = None
    _name_size = None

    # make sure some rar5 fields are always present
    file_redir = None
    blake2sp_hash = None

    endarc_datacrc = None
    endarc_volnr = None

    old_sub_type = None

    def _must_disable_hack(self):
        if self.type == RAR_BLOCK_FILE:
            if self.flags & RAR_FILE_PASSWORD:
                return True
            elif self.flags & (RAR_FILE_SPLIT_BEFORE | RAR_FILE_SPLIT_AFTER):
                return True
        elif self.type == RAR_BLOCK_MAIN:
            if self.flags & (RAR_MAIN_SOLID | RAR_MAIN_PASSWORD):
                return True
        return False

    def is_dir(self):
        """Returns True if entry is a directory."""
        if self.type == RAR_BLOCK_FILE and not self.is_symlink():
            return (self.flags & RAR_FILE_DIRECTORY) == RAR_FILE_DIRECTORY
        return False

    def is_symlink(self):
        """Returns True if entry is a symlink."""
        return (
            self.type == RAR_BLOCK_FILE and
            self.host_os == RAR_OS_UNIX and
            self.mode & 0xF000 == 0xA000
        )

    def is_file(self):
        """Returns True if entry is a normal file."""
        return (
            self.type == RAR_BLOCK_FILE and
            not (self.is_dir() or self.is_symlink())
        )


class Rar5Info(RarInfo):
    """Shared fields for RAR5 records.
    """
    extract_version = 50
    header_crc = None
    header_size = None
    header_offset = None
    data_offset = None

    # type=all
    block_type = None
    block_flags = None
    add_size = 0
    block_extra_size = 0

    # type=MAIN
    volume_number = None
    _md_class = None
    _md_expect = None

    def _must_disable_hack(self):
        return False


class Rar5BaseFile(Rar5Info):
    """Shared sturct for file & service record.
    """
    type = -1
    file_flags = None
    file_encryption = (0, 0, 0, b"", b"", b"")
    file_compress_flags = None
    file_redir = None
    file_owner = None
    file_version = None
    blake2sp_hash = None

    def _must_disable_hack(self):
        if self.flags & RAR_FILE_PASSWORD:
            return True
        if self.block_flags & (RAR5_BLOCK_FLAG_SPLIT_BEFORE | RAR5_BLOCK_FLAG_SPLIT_AFTER):
            return True
        if self.file_compress_flags & RAR5_COMPR_SOLID:
            return True
        if self.file_redir:
            return True
        return False


class Rar5FileInfo(Rar5BaseFile):
    """RAR5 file record.
    """
    type = RAR_BLOCK_FILE

    def is_symlink(self):
        """Returns True if entry is a symlink."""
        # pylint: disable=unsubscriptable-object
        return (
            self.file_redir is not None and
            self.file_redir[0] in (
                RAR5_XREDIR_UNIX_SYMLINK,
                RAR5_XREDIR_WINDOWS_SYMLINK,
                RAR5_XREDIR_WINDOWS_JUNCTION,
            )
        )

    def is_file(self):
        """Returns True if entry is a normal file."""
        return not (self.is_dir() or self.is_symlink())

    def is_dir(self):
        """Returns True if entry is a directory."""
        if not self.file_redir:
            if self.file_flags & RAR5_FILE_FLAG_ISDIR:
                return True
        return False


class Rar5ServiceInfo(Rar5BaseFile):
    """RAR5 service record.
    """
    type = RAR_BLOCK_SUB


class Rar5MainInfo(Rar5Info):
    """RAR5 archive main record.
    """
    type = RAR_BLOCK_MAIN
    main_flags = None
    main_volume_number = None

    def _must_disable_hack(self):
        if self.main_flags & RAR5_MAIN_FLAG_SOLID:
            return True
        return False


class Rar5EncryptionInfo(Rar5Info):
    """RAR5 archive header encryption record.
    """
    type = RAR5_BLOCK_ENCRYPTION
    encryption_algo = None
    encryption_flags = None
    encryption_kdf_count = None
    encryption_salt = None
    encryption_check_value = None

    def needs_password(self):
        return True


class Rar5EndArcInfo(Rar5Info):
    """RAR5 end of archive record.
    """
    type = RAR_BLOCK_ENDARC
    endarc_flags = None
