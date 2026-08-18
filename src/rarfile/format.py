"""RAR file format parser.
"""

import os
import re
import struct
import sys
from binascii import crc32
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from struct import Struct
from tempfile import mkstemp
from typing import TypedDict, cast

from . import config
from .backend import custom_popen, tool_setup
from .bits import (
    DOS_MODE_ARCHIVE, RAR5_BLOCK_ENCRYPTION, RAR5_BLOCK_ENDARC,
    RAR5_BLOCK_FILE, RAR5_BLOCK_FLAG_DATA_AREA, RAR5_BLOCK_FLAG_EXTRA_DATA,
    RAR5_BLOCK_FLAG_SKIP_IF_UNKNOWN, RAR5_BLOCK_FLAG_SPLIT_AFTER,
    RAR5_BLOCK_FLAG_SPLIT_BEFORE, RAR5_BLOCK_MAIN, RAR5_BLOCK_SERVICE,
    RAR5_COMPR_SOLID, RAR5_ENC_FLAG_HAS_CHECKVAL, RAR5_ENDARC_FLAG_NEXT_VOL,
    RAR5_FILE_FLAG_HAS_CRC32, RAR5_FILE_FLAG_HAS_MTIME, RAR5_FILE_FLAG_ISDIR,
    RAR5_ID, RAR5_MAIN_FLAG_HAS_VOLNR, RAR5_MAIN_FLAG_ISVOL,
    RAR5_MAIN_FLAG_RECOVERY, RAR5_MAIN_FLAG_SOLID, RAR5_OS_WINDOWS,
    RAR5_PW_CHECK_SIZE, RAR5_PW_SUM_SIZE, RAR5_XENC_CHECKVAL,
    RAR5_XENC_CIPHER_AES256, RAR5_XENC_TWEAKED, RAR5_XFILE_ENCRYPTION,
    RAR5_XFILE_HASH, RAR5_XFILE_OWNER, RAR5_XFILE_REDIR, RAR5_XFILE_SERVICE,
    RAR5_XFILE_TIME, RAR5_XFILE_VERSION, RAR5_XHASH_BLAKE2SP,
    RAR5_XOWNER_GID, RAR5_XOWNER_GNAME, RAR5_XOWNER_UID, RAR5_XOWNER_UNAME,
    RAR5_XREDIR_FILE_COPY, RAR5_XREDIR_HARD_LINK, RAR5_XREDIR_UNIX_SYMLINK,
    RAR5_XREDIR_WINDOWS_JUNCTION, RAR5_XREDIR_WINDOWS_SYMLINK,
    RAR5_XTIME_HAS_ATIME, RAR5_XTIME_HAS_CTIME, RAR5_XTIME_HAS_MTIME,
    RAR5_XTIME_UNIXTIME, RAR5_XTIME_UNIXTIME_NS, RAR_BLOCK_ENDARC,
    RAR_BLOCK_FILE, RAR_BLOCK_MAIN, RAR_BLOCK_MARK, RAR_BLOCK_OLD_AUTH,
    RAR_BLOCK_OLD_COMMENT, RAR_BLOCK_OLD_EXTRA, RAR_BLOCK_OLD_SUB,
    RAR_BLOCK_SUB, RAR_ENDARC_DATACRC, RAR_ENDARC_NEXT_VOLUME,
    RAR_ENDARC_VOLNR, RAR_FILE_COMMENT, RAR_FILE_DICTMASK,
    RAR_FILE_DIRECTORY, RAR_FILE_EXTTIME, RAR_FILE_LARGE, RAR_FILE_PASSWORD,
    RAR_FILE_SALT, RAR_FILE_SOLID, RAR_FILE_SPLIT_AFTER,
    RAR_FILE_SPLIT_BEFORE, RAR_FILE_UNICODE, RAR_FILE_VERSION, RAR_ID,
    RAR_LONG_BLOCK, RAR_M0, RAR_MAIN_COMMENT, RAR_MAIN_ENCRYPTVER,
    RAR_MAIN_FIRSTVOLUME, RAR_MAIN_NEWNUMBERING, RAR_MAIN_PASSWORD,
    RAR_MAIN_RECOVERY, RAR_MAIN_SOLID, RAR_MAIN_VOLUME, RAR_MAX_COMMENT,
    RAR_MAX_KDF_SHIFT, RAR_OLD_SUB_MAC, RAR_OLD_SUB_UNIX, RAR_OS_MSDOS,
    RAR_OS_UNIX, RAR_OS_WIN32, RAR_SKIP_IF_UNKNOWN,
)
from .crypto import (
    AES_CBC_Decrypt, Blake2SP, CRC32Context, HashContext,
    HeaderDecrypt, NoHashContext, rar3_s2k, rar5_s2k,
)
from .errors import (
    BadRarFile, BadRarName, NeedFirstVolume,
    NoRarEntry, NotRarFile, RarWrongPassword,
)
from .info import (
    FileEncryption, Rar3EndArcInfo, Rar3GenericInfo, Rar3Info, Rar3MainInfo,
    Rar3SubInfo, Rar5BaseFile, Rar5EncryptionInfo, Rar5EndArcInfo,
    Rar5FileInfo, Rar5MainInfo, Rar5ServiceInfo, RarEntry, RarInfo,
)
from .stream import BytesReader, DirectReader, PipeReader, RarExtFile
from .utils import (
    DateTuple, FileLike, PathLike, UnicodeFilename, XFile, is_filelike,
    membuf_tempfile, parse_dos_time, to_datetime, to_nsdatetime,
)

if sys.version_info < (3, 12):
    from typing_extensions import NotRequired
else:
    from typing import NotRequired


# export only interesting items
__all__ = ("CommonParser", "RAR3Parser", "RAR5Parser")


#
# File format parsing
#

class CommonArgs(TypedDict):
    """Low-level constructor fields common to every archive entry.
    """

    flags: int
    header_crc: int
    header_size: int
    header_offset: int
    data_offset: int
    add_size: int

    # RAR3 sets a normalized block type here; RAR5 relies on subclass defaults
    type: NotRequired[int]

    # RAR5 low-level framing, absent (-> None / 0) for RAR3
    block_type: NotRequired[int]
    block_flags: NotRequired[int]
    block_extra_size: NotRequired[int]


class InfoArgs(CommonArgs):
    """Public file fields, in addition to the common low-level ones.
    """

    filename: str
    orig_filename: bytes
    file_size: int
    compress_size: int
    extract_version: int
    mode: int
    host_os: int
    compress_type: int

    date_time: NotRequired[DateTuple]
    mtime: NotRequired[datetime | None]
    ctime: NotRequired[datetime | None]
    atime: NotRequired[datetime | None]
    arctime: NotRequired[datetime | None]
    comment: NotRequired[str | None]
    CRC: NotRequired[int]
    blake2sp_hash: NotRequired[bytes]
    file_redir: NotRequired[tuple[int, int, str]]
    file_version: NotRequired[tuple[int, int]]
    file_owner: NotRequired[tuple[bytes | None, bytes | None, int | None, int | None]]
    _md_class: NotRequired[type[HashContext]]
    _md_expect: NotRequired[int | bytes | None]


class CommonParser:
    """Shared parser parts."""
    _main: RarEntry | None = None
    _hdrenc_main: Rar5EncryptionInfo | None = None

    _needs_password: bool = False
    _fd: XFile | None = None
    _expect_sig: bytes = b""
    _parse_error: str | None = None
    _password: str | None = None
    comment: str | None = None

    def __init__(self, rarfile: PathLike | FileLike, password: str | None, crc_check: bool, charset: str | None, strict: bool,
                 info_cb: Callable[[RarEntry], None] | None, sfx_offset: int, part_only: bool):
        self._rarfile = rarfile
        self._password = password
        self._crc_check = crc_check
        self._charset = charset or config.DEFAULT_CHARSET
        self._strict = strict
        self._info_callback = info_cb
        self._info_list: list[RarInfo] = []
        self._info_map: dict[str, RarInfo] = {}
        self._vol_list: list[PathLike | FileLike] = []
        self._sfx_offset = sfx_offset
        self._part_only = part_only

    def is_solid(self) -> bool:
        """Returns True if archive uses solid compression.
        """
        if self._main:
            if self._main.flags & RAR_MAIN_SOLID:
                return True
        return False

    def has_header_encryption(self) -> bool:
        """Returns True if headers are encrypted
        """
        if self._hdrenc_main:
            return True
        if self._main:
            if self._main.flags & RAR_MAIN_PASSWORD:
                return True
        return False

    def setpassword(self, pwd: str | None) -> None:
        """Set cached password."""
        self._password = pwd

    def volumelist(self) -> Sequence[PathLike | FileLike]:
        """Volume files"""
        return self._vol_list

    def needs_password(self) -> bool:
        """Is password required"""
        return self._needs_password

    def strerror(self) -> str | None:
        """Last error"""
        return self._parse_error

    def infolist(self) -> Sequence[RarInfo]:
        """List of RarInfo records.
        """
        return self._info_list

    def getinfo(self, member: str | Path | RarInfo) -> RarInfo:
        """Return RarInfo for filename
        """
        if isinstance(member, RarInfo):
            fname = member.filename
        elif isinstance(member, Path):
            fname = str(member)
        elif isinstance(member, str):
            fname = member
        else:
            raise TypeError("unexpect type")

        if fname.endswith("/"):
            fname = fname.rstrip("/")

        try:
            return self._info_map[fname]
        except KeyError:
            raise NoRarEntry("No such file: %s" % fname) from None

    def getinfo_orig(self, member: str | Path | RarInfo) -> RarInfo:
        inf = self.getinfo(member)
        if inf.file_redir:
            redir_type, _redir_flags, redir_name = inf.file_redir
            # cannot leave to unrar as it expects copied file to exist
            if redir_type in (RAR5_XREDIR_FILE_COPY, RAR5_XREDIR_HARD_LINK):
                inf = self.getinfo(redir_name)
        return inf

    def parse(self) -> None:
        """Process file."""
        self._fd = None
        try:
            self._parse_real()
        finally:
            if self._fd:
                self._fd.close()
                self._fd = None

    def _parse_real(self) -> None:
        """Actually read file.
        """
        fd = XFile(self._rarfile)
        self._fd = fd
        fd.seek(self._sfx_offset, 0)
        sig = fd.read(len(self._expect_sig))
        if sig != self._expect_sig:
            raise NotRarFile("Not a Rar archive")

        volume = 0  # first vol (.rar) is 0
        more_vols = False
        endarc = False
        volfile = self._rarfile
        self._vol_list = [self._rarfile]
        raise_need_first_vol = False
        while True:
            if endarc:
                h = None    # don"t read past ENDARC
            else:
                h = self._parse_header(fd)
            if not h:
                if raise_need_first_vol:
                    # did not find ENDARC with VOLNR
                    raise NeedFirstVolume("Need to start from first volume", None)
                if more_vols and not self._part_only:
                    volume += 1
                    fd.close()
                    try:
                        volfile = self._next_volname(volfile)
                        fd = XFile(volfile)
                    except OSError:
                        self._set_error("Cannot open next volume: %s", str(volfile))
                        break
                    self._fd = fd
                    sig = fd.read(len(self._expect_sig))
                    if sig != self._expect_sig:
                        self._set_error("Invalid volume sig: %s", volfile)
                        break
                    more_vols = False
                    endarc = False
                    self._vol_list.append(volfile)
                    self._main = None
                    self._hdrenc_main = None
                    continue
                break
            h.volume = volume
            h.volume_file = volfile

            if h.type == RAR_BLOCK_MAIN and not self._main:
                self._main = h
                if volume == 0 and (h.flags & RAR_MAIN_NEWNUMBERING) and not self._part_only:
                    # RAR 2.x does not set FIRSTVOLUME,
                    # so check it only if NEWNUMBERING is used
                    if (h.flags & RAR_MAIN_FIRSTVOLUME) == 0:
                        if isinstance(h, Rar5MainInfo) and h.main_volume_number is not None:
                            # rar5 may have more info
                            raise NeedFirstVolume(
                                "Need to start from first volume (current: %r)"
                                % (h.main_volume_number,),
                                h.main_volume_number
                            )
                        # delay raise until we have volnr from ENDARC
                        raise_need_first_vol = True
                if h.flags & RAR_MAIN_PASSWORD:
                    self._needs_password = True
                    if not self._password:
                        break
            elif h.type == RAR_BLOCK_ENDARC:
                # use flag, but also allow RAR 2.x logic below to trigger
                if h.flags & RAR_ENDARC_NEXT_VOLUME:
                    more_vols = True
                endarc = True
                if raise_need_first_vol and (h.flags & RAR_ENDARC_VOLNR) > 0:
                    assert isinstance(h, Rar3EndArcInfo)
                    raise NeedFirstVolume(
                        "Need to start from first volume (current: %r)"
                        % (h.endarc_volnr,),
                        h.endarc_volnr
                    )
            elif h.type == RAR_BLOCK_FILE:
                # RAR 2.x does not write RAR_BLOCK_ENDARC
                if h.flags & RAR_FILE_SPLIT_AFTER:
                    more_vols = True
                # RAR 2.x does not set RAR_MAIN_FIRSTVOLUME
                if volume == 0 and h.flags & RAR_FILE_SPLIT_BEFORE:
                    if not self._part_only:
                        raise_need_first_vol = True

            if h.needs_password():
                self._needs_password = True

            # store it
            self.process_entry(fd, h)

            if self._info_callback:
                self._info_callback(h)

            # go to next header
            if h.add_size > 0:
                fd.seek(h.data_offset + h.add_size, 0)

    def process_entry(self, fd: XFile, item: RarEntry) -> None:
        """Examine item, add into lookup cache."""
        raise NotImplementedError()

    def _decrypt_header(self, fd: FileLike) -> FileLike:
        raise NotImplementedError("_decrypt_header")

    def _parse_block_header(self, fd: FileLike) -> RarEntry | None:
        raise NotImplementedError("_parse_block_header")

    def _open_hack(self, inf: RarInfo, pwd: str | None) -> RarExtFile:
        raise NotImplementedError("_open_hack")

    def _parse_header(self, fd: FileLike) -> RarEntry | None:
        """Read single header
        """
        try:
            # handle encrypted headers
            reader: FileLike = fd
            if (self._main and self._main.flags & RAR_MAIN_PASSWORD) or self._hdrenc_main:
                if not self._password:
                    return None
                reader = self._decrypt_header(fd)

            # now read actual header
            return self._parse_block_header(reader)
        except struct.error:
            self._set_error("Broken header in RAR file")
            return None

    def _next_volname(self, volfile: PathLike | FileLike) -> str:
        """Given current vol name, construct next one
        """
        if is_filelike(volfile):
            raise OSError("Working on single FD")
        assert self._main is not None
        name = cast(str, volfile)
        if self._main.flags & RAR_MAIN_NEWNUMBERING:
            return _next_newvol(name)
        return _next_oldvol(name)

    def _set_error(self, msg: str, *args: str | int) -> None:
        if args:
            msg = msg % args
        self._parse_error = msg
        if self._strict:
            raise BadRarFile(msg)

    def open(self, inf: RarInfo, pwd: str | None) -> RarExtFile:
        """Return stream object for file data."""

        if inf.file_redir:
            redir_type, _redir_flags, redir_name = inf.file_redir
            # cannot leave to unrar as it expects copied file to exist
            if redir_type in (RAR5_XREDIR_FILE_COPY, RAR5_XREDIR_HARD_LINK):
                inf = self.getinfo(redir_name)
                if not inf:
                    raise BadRarFile("cannot find copied file")
            elif redir_type in (
                RAR5_XREDIR_UNIX_SYMLINK, RAR5_XREDIR_WINDOWS_SYMLINK,
                RAR5_XREDIR_WINDOWS_JUNCTION,
            ):
                data = redir_name.encode("utf8")
                return BytesReader(data, inf)
        if inf.flags and inf.flags & RAR_FILE_SPLIT_BEFORE:
            raise NeedFirstVolume(
                "Partial file, please start from first volume: " + inf.filename, None)

        # is temp write usable?
        use_hack = 1
        if not self._main:
            use_hack = 0
        elif self._main._must_disable_hack():
            use_hack = 0
        elif inf._must_disable_hack():
            use_hack = 0
        elif is_filelike(self._rarfile):
            pass
        elif inf.file_size and inf.file_size > config.HACK_SIZE_LIMIT:
            use_hack = 0
        elif not config.USE_EXTRACT_HACK:
            use_hack = 0

        # now extract
        if inf.compress_type == RAR_M0 and (inf.flags & RAR_FILE_PASSWORD) == 0 and inf.file_redir is None:
            return self._open_clear(inf)
        elif use_hack:
            return self._open_hack(inf, pwd)
        elif is_filelike(self._rarfile):
            return self._open_unrar_membuf(self._rarfile, inf, pwd)
        else:
            return self._open_unrar(self._rarfile, inf, pwd)

    def _open_clear(self, inf: RarInfo) -> RarExtFile:
        if config.FORCE_TOOL:
            if is_filelike(self._rarfile):
                return self._open_unrar_membuf(self._rarfile, inf, None)
            return self._open_unrar(self._rarfile, inf)
        return DirectReader(self, inf)

    def _open_hack_core(self, inf: RarInfo, pwd: str | None, prefix: bytes, suffix: bytes) -> RarExtFile:
        assert inf.compress_size is not None and inf.header_size is not None
        assert inf.volume_file is not None and inf.header_offset is not None

        size = inf.compress_size + inf.header_size
        rf = XFile(inf.volume_file, 0)
        rf.seek(inf.header_offset)

        tmpfd, tmpname = mkstemp(suffix=".rar", dir=config.HACK_TMP_DIR)
        tmpf = os.fdopen(tmpfd, "wb")

        try:
            tmpf.write(prefix)
            while size > 0:
                if size > config.BSIZE:
                    buf = rf.read(config.BSIZE)
                else:
                    buf = rf.read(size)
                if not buf:
                    raise BadRarFile("read failed: " + inf.filename)
                tmpf.write(buf)
                size -= len(buf)
            tmpf.write(suffix)
            tmpf.close()
            rf.close()
        except BaseException:
            rf.close()
            tmpf.close()
            os.unlink(tmpname)
            raise

        return self._open_unrar(tmpname, inf, pwd, tmpname)

    def _open_unrar_membuf(self, memfile: FileLike, inf: RarInfo, pwd: str | None) -> RarExtFile:
        """Write in-memory archive to temp file, needed for solid archives.
        """
        tmpname = membuf_tempfile(memfile)
        return self._open_unrar(tmpname, inf, pwd, tmpname, force_file=True)

    def _open_unrar(self, rarfile: PathLike, inf: RarInfo, pwd: str | None = None,
                    tmpfile: str | None = None, force_file: bool = False) -> RarExtFile:
        """Extract using unrar
        """
        setup = tool_setup()

        # not giving filename avoids encoding related problems
        fn = None
        if not tmpfile or force_file:
            fn = inf.filename.replace("/", os.path.sep)

        # read from unrar pipe
        cmd = setup.open_cmdline(pwd, os.fsdecode(rarfile), fn)
        return PipeReader(inf, cmd, tmpfile)


#
# RAR3 format
#

class RAR3Parser(CommonParser):
    """Parse RAR3 file format.
    """
    _expect_sig = RAR_ID
    _last_aes_key: tuple[bytes, bytes, bytes] | None = None   # (salt, key, iv)

    def _decrypt_header(self, fd: FileLike) -> FileLike:
        AES_CBC_Decrypt.load()

        assert self._password is not None
        salt = fd.read(8)
        cached = self._last_aes_key
        if cached is not None and cached[0] == salt:
            key, iv = cached[1], cached[2]
        else:
            key, iv = rar3_s2k(self._password, salt)
            self._last_aes_key = (salt, key, iv)
        return HeaderDecrypt(fd, key, iv)

    def _parse_block_header(self, fd: FileLike) -> RarEntry | None:
        """Parse common block header
        """
        header_offset = fd.tell()

        # read and parse base header
        buf = fd.read(S_BLK_HDR.size)
        if not buf:
            return None
        if len(buf) < S_BLK_HDR.size:
            self._set_error("Unexpected EOF when reading header")
            return None
        header_crc, btype, flags, header_size = S_BLK_HDR.unpack_from(buf)

        # read full header
        if header_size > S_BLK_HDR.size:
            hdata = buf + fd.read(header_size - S_BLK_HDR.size)
        else:
            hdata = buf
        data_offset = fd.tell()

        # unexpected EOF?
        if len(hdata) != header_size:
            self._set_error("Unexpected EOF when reading header")
            return None

        pos = S_BLK_HDR.size

        # block has data assiciated with it?
        if flags & RAR_LONG_BLOCK:
            add_size, pos = load_le32(hdata, pos)
        else:
            add_size = 0

        common_args: CommonArgs = {
            "header_offset": header_offset,
            "header_crc": header_crc,
            "type": btype,
            "flags": flags,
            "header_size": header_size,
            "data_offset": data_offset,
            "add_size": add_size,
        }

        # mark has no CRC-protected body
        if btype == RAR_BLOCK_MARK:
            return Rar3GenericInfo(**common_args)

        # parse interesting ones, decide header boundaries for crc
        h: RarEntry
        if btype == RAR_BLOCK_MAIN:
            pos += 6
            if flags & RAR_MAIN_ENCRYPTVER:
                pos += 1
            crc_pos = pos
            comment = None
            if flags & RAR_MAIN_COMMENT:
                comment, _ = self._parse_subblocks(hdata, pos)
            h = Rar3MainInfo(comment=comment, **common_args)
        elif btype in (RAR_BLOCK_FILE, RAR_BLOCK_SUB):
            file_args, salt, name_size, pos = self._parse_file_header(hdata, pos - 4, common_args)
            if btype == RAR_BLOCK_FILE:
                crc_pos = pos
                if flags & RAR_FILE_COMMENT:
                    comment, pos = self._parse_subblocks(hdata, pos)
                    file_args["comment"] = comment
                h = Rar3Info(salt=salt, _name_size=name_size, **file_args)
            else:
                crc_pos = header_size
                h = Rar3SubInfo(salt=salt, _name_size=name_size, **file_args)
            if h.is_dir():
                h.filename = h.filename + "/"
        elif btype == RAR_BLOCK_OLD_AUTH:
            pos += 8
            crc_pos = pos
            h = Rar3GenericInfo(**common_args)
        elif btype == RAR_BLOCK_OLD_EXTRA:
            pos += 7
            crc_pos = pos
            h = Rar3GenericInfo(**common_args)
        elif btype == RAR_BLOCK_OLD_SUB:
            old_sub_type = self._parse_old_subblock(hdata, pos)

            # these types do not have their own data CRC,
            # so data was included in header CRC.
            if old_sub_type in (RAR_OLD_SUB_UNIX, RAR_OLD_SUB_MAC):
                # skip CRC check, it requires to read data part
                return Rar3GenericInfo(old_sub_type=old_sub_type, **common_args)

            crc_pos = header_size
            h = Rar3GenericInfo(old_sub_type=old_sub_type, **common_args)
        elif btype == RAR_BLOCK_ENDARC:
            endarc_datacrc = None
            endarc_volnr = None
            if flags & RAR_ENDARC_DATACRC:
                endarc_datacrc, pos = load_le32(hdata, pos)
            if flags & RAR_ENDARC_VOLNR:
                endarc_volnr = S_SHORT.unpack_from(hdata, pos)[0]
                pos += 2
            crc_pos = header_size
            h = Rar3EndArcInfo(endarc_datacrc=endarc_datacrc,
                               endarc_volnr=endarc_volnr, **common_args)
        else:
            crc_pos = header_size
            h = Rar3GenericInfo(**common_args)

        # calculate crc
        crcdat = hdata[2:crc_pos]
        calc_crc = crc32(crcdat) & 0xFFFF

        # return good header
        if header_crc == calc_crc:
            return h

        # header parsing failed.
        self._set_error("Header CRC error (%02x): exp=%x got=%x (xlen = %d)",
                        btype, header_crc, calc_crc, len(crcdat))

        # instead panicing, send eof
        return None

    def _parse_file_header(self, hdata: bytes, pos: int, common_args: CommonArgs
                           ) -> tuple[InfoArgs, bytes | None, int, int]:
        """Read file-specific header, returning constructor kwargs.
        """
        flags = common_args["flags"]

        fld = S_FILE_HDR.unpack_from(hdata, pos)
        pos += S_FILE_HDR.size

        compress_size = fld[0]
        file_size = fld[1]
        host_os = fld[2]
        crc = fld[3]
        date_time = parse_dos_time(fld[4])
        extract_version = fld[5]
        compress_type = fld[6]
        name_size = fld[7]
        mode = fld[8]

        add_size = common_args["add_size"]
        if flags & RAR_FILE_LARGE:
            h1, pos = load_le32(hdata, pos)
            h2, pos = load_le32(hdata, pos)
            compress_size |= h1 << 32
            file_size |= h2 << 32
            add_size = compress_size

        name, pos = load_bytes(hdata, name_size, pos)
        if flags & RAR_FILE_UNICODE and b"\0" in name:
            # stored in custom encoding
            nul = name.find(b"\0")
            orig_filename = name[:nul]
            u = UnicodeFilename(orig_filename, name[nul + 1:])
            filename = u.decode()

            # if parsing failed fall back to simple name
            if u.failed:
                filename = self._decode(orig_filename)
        elif flags & RAR_FILE_UNICODE:
            # stored in UTF8
            orig_filename = name
            filename = name.decode("utf8", "replace")
        else:
            nul = name.find(b"\0")
            if nul >= 0:
                name = name[:nul]
            # stored in random encoding
            orig_filename = name
            filename = self._decode(name)
        filename = filename.replace("\\", "/").rstrip("/")

        # change separator, dir suffix is added by caller
        file_args: InfoArgs = {
            "type": common_args.get("type") or 0,
            "flags": flags,
            "header_crc": common_args["header_crc"],
            "header_size": common_args["header_size"],
            "header_offset": common_args["header_offset"],
            "data_offset": common_args["data_offset"],
            "add_size": add_size,
            "host_os": host_os,
            "CRC": crc,
            "date_time": date_time,
            "mtime": to_datetime(date_time),
            "extract_version": extract_version,
            "compress_type": compress_type,
            "mode": mode,
            "compress_size": compress_size,
            "file_size": file_size,
            "orig_filename": orig_filename,
            "filename": filename,
            "_md_class": CRC32Context,
            "_md_expect": crc,
        }

        salt = None
        if flags & RAR_FILE_SALT:
            salt, pos = load_bytes(hdata, 8, pos)

        # optional extended time stamps
        if flags & RAR_FILE_EXTTIME:
            pos = _parse_ext_time(file_args, hdata, pos)
        else:
            file_args["mtime"] = None
            file_args["atime"] = None
            file_args["ctime"] = None
            file_args["arctime"] = None

        return file_args, salt, name_size, pos

    def _parse_old_subblock(self, hdata: bytes, pos: int) -> int:
        """Parse RAR2 subblock type
        """
        fields = S_OLD_SUBBLOCK_HDR.unpack_from(hdata, pos)
        old_sub_type: int = fields[0]
        return old_sub_type

    def _parse_subblocks(self, hdata: bytes, pos: int) -> tuple[str | None, int]:
        """Find old-style comment subblock
        """
        comment = None
        while pos < len(hdata):
            # ordinary block header
            t = S_BLK_HDR.unpack_from(hdata, pos)
            ___scrc, stype, sflags, slen = t
            pos_next = pos + slen
            pos += S_BLK_HDR.size

            # corrupt header
            if pos_next < pos:
                break

            # followed by block-specific header
            if stype == RAR_BLOCK_OLD_COMMENT and pos + S_COMMENT_HDR.size <= pos_next:
                declen, ver, meth, crc = S_COMMENT_HDR.unpack_from(hdata, pos)
                if declen > RAR_MAX_COMMENT:
                    pos = pos_next
                    continue
                pos += S_COMMENT_HDR.size
                data = hdata[pos: pos_next]
                cmt = rar3_decompress(ver, meth, data, declen, sflags,
                                      crc, self._password)
                if not self._crc_check or (crc32(cmt) & 0xFFFF == crc):
                    comment = self._decode_comment(cmt)

            pos = pos_next
        return comment, pos

    def _read_comment_v3(self, inf: Rar3Info, pwd: str | None = None) -> str | None:
        assert inf.volume_file is not None and inf.compress_size is not None

        if inf.compress_size > RAR_MAX_COMMENT:
            return None
        if inf.file_size > RAR_MAX_COMMENT:
            return None

        # read data
        with XFile(inf.volume_file) as rf:
            rf.seek(inf.data_offset)
            data = rf.read(inf.compress_size)

        # decompress
        cmt = rar3_decompress(inf.extract_version, inf.compress_type, data,
                              inf.file_size, inf.flags, inf.CRC or 0, pwd, inf.salt)

        # check crc
        if self._crc_check:
            crc = crc32(cmt)
            if crc != inf.CRC:
                return None

        return self._decode_comment(cmt)

    def _decode(self, val: bytes) -> str:
        for c in config.TRY_ENCODINGS:
            try:
                return val.decode(c)
            except UnicodeError:
                pass
        return val.decode(self._charset, "replace")

    def _decode_comment(self, val: bytes) -> str:
        return self._decode(val)

    def process_entry(self, fd: XFile, item: RarEntry) -> None:
        if item.type == RAR_BLOCK_FILE:
            assert isinstance(item, Rar3Info)
            # use only first part
            if item.flags & RAR_FILE_VERSION:
                pass    # skip old versions
            elif (item.flags & RAR_FILE_SPLIT_BEFORE) == 0:
                self._info_map[item.filename.rstrip("/")] = item
                self._info_list.append(item)
            elif len(self._info_list) > 0:
                # final crc is in last block
                old = self._info_list[-1]
                old.CRC = item.CRC
                old._md_expect = item._md_expect
                assert old.compress_size is not None and item.compress_size is not None
                old.compress_size += item.compress_size

        # parse new-style comment
        elif item.type == RAR_BLOCK_SUB:
            assert isinstance(item, Rar3Info)
            if item.filename != "CMT":
                pass
            elif item.flags & (RAR_FILE_SPLIT_BEFORE | RAR_FILE_SPLIT_AFTER):
                pass
            elif item.flags & RAR_FILE_SOLID:
                # file comment
                cmt = self._read_comment_v3(item, self._password)
                if len(self._info_list) > 0:
                    old = self._info_list[-1]
                    old.comment = cmt
            else:
                # archive comment
                cmt = self._read_comment_v3(item, self._password)
                self.comment = cmt

        elif item.type == RAR_BLOCK_MAIN:
            assert isinstance(item, Rar3MainInfo)
            if item.flags & RAR_MAIN_COMMENT:
                self.comment = item.comment
            if item.flags & RAR_MAIN_PASSWORD:
                self._needs_password = True

    # put file compressed data into temporary .rar archive, and run
    # unrar on that, thus avoiding unrar going over whole archive
    def _open_hack(self, inf: RarInfo, pwd: str | None) -> RarExtFile:
        # create main header: crc, type, flags, size, res1, res2
        prefix = RAR_ID + S_BLK_HDR.pack(0x90CF, 0x73, 0, 13) + b"\0" * (2 + 4)
        return self._open_hack_core(inf, pwd, prefix, b"")


#
# RAR5 format
#

class RAR5Parser(CommonParser):
    """Parse RAR5 format.
    """
    _expect_sig = RAR5_ID

    # AES encrypted headers
    _last_aes256_key: tuple[int, bytes, bytes] | None = None   # (kdf_count, salt, key)

    def _get_utf8_password(self) -> bytes:
        pwd = self._password
        assert pwd is not None
        return pwd.encode("utf8")

    def _gen_key(self, kdf_count: int, salt: bytes) -> bytes:
        cached = self._last_aes256_key
        if cached is not None and cached[:2] == (kdf_count, salt):
            return cached[2]
        if kdf_count > RAR_MAX_KDF_SHIFT:
            raise BadRarFile("Too large kdf_count")
        pwd = self._get_utf8_password()
        key = rar5_s2k(pwd, salt, 1 << kdf_count)
        self._last_aes256_key = (kdf_count, salt, key)
        return key

    def _decrypt_header(self, fd: FileLike) -> FileLike:
        AES_CBC_Decrypt.load()

        h = self._hdrenc_main
        assert h is not None
        key = self._gen_key(h.encryption_kdf_count, h.encryption_salt)
        iv = fd.read(16)
        return HeaderDecrypt(fd, key, iv)

    def _parse_block_header(self, fd: FileLike) -> RarEntry | None:
        """Parse common block header
        """
        header_offset = fd.tell()

        preload = 4 + 1
        start_bytes = fd.read(preload)
        if len(start_bytes) < preload:
            self._set_error("Unexpected EOF when reading header")
            return None
        while start_bytes[-1] & 0x80:
            b = fd.read(1)
            if not b:
                self._set_error("Unexpected EOF when reading header")
                return None
            start_bytes += b
        header_crc, pos = load_le32(start_bytes, 0)
        hdrlen, pos = load_vint(start_bytes, pos)
        if hdrlen > 2 * 1024 * 1024:
            return None
        header_size = pos + hdrlen

        # read full header, check for EOF
        hdata = start_bytes + fd.read(header_size - len(start_bytes))
        if len(hdata) != header_size:
            self._set_error("Unexpected EOF when reading header")
            return None
        data_offset = fd.tell()

        calc_crc = crc32(memoryview(hdata)[4:])
        if header_crc != calc_crc:
            # header parsing failed.
            self._set_error("Header CRC error: exp=%x got=%x (xlen = %d)",
                            header_crc, calc_crc, len(hdata))
            return None

        block_type, pos = load_vint(hdata, pos)

        common_args, pos = self._parse_block_common(hdata, header_offset, data_offset)

        if block_type == RAR5_BLOCK_MAIN:
            return self._parse_main_block(hdata, pos, common_args)
        elif block_type == RAR5_BLOCK_FILE:
            return self._parse_file_block(hdata, pos, common_args, Rar5FileInfo)
        elif block_type == RAR5_BLOCK_SERVICE:
            return self._parse_file_block(hdata, pos, common_args, Rar5ServiceInfo)
        elif block_type == RAR5_BLOCK_ENCRYPTION:
            return self._parse_encryption_block(hdata, pos, common_args)
        elif block_type == RAR5_BLOCK_ENDARC:
            return self._parse_endarc_block(hdata, pos, common_args)
        return None

    def _parse_block_common(self, hdata: bytes, header_offset: int, data_offset: int
                            ) -> tuple[CommonArgs, int]:
        header_crc, pos = load_le32(hdata, 0)
        hdrlen, pos = load_vint(hdata, pos)
        header_size = hdrlen + pos
        block_type, pos = load_vint(hdata, pos)
        block_flags, pos = load_vint(hdata, pos)

        block_extra_size = 0
        add_size = 0
        if block_flags & RAR5_BLOCK_FLAG_EXTRA_DATA:
            block_extra_size, pos = load_vint(hdata, pos)
        if block_flags & RAR5_BLOCK_FLAG_DATA_AREA:
            add_size, pos = load_vint(hdata, pos)

        flags = 0
        if block_flags & RAR5_BLOCK_FLAG_SKIP_IF_UNKNOWN:
            flags |= RAR_SKIP_IF_UNKNOWN
        if block_flags & RAR5_BLOCK_FLAG_DATA_AREA:
            flags |= RAR_LONG_BLOCK

        common_args: CommonArgs = {
            "header_crc": header_crc,
            "header_size": header_size,
            "header_offset": header_offset,
            "data_offset": data_offset,
            "block_type": block_type,
            "block_flags": block_flags,
            "block_extra_size": block_extra_size,
            "add_size": add_size,
            "flags": flags,
        }
        return common_args, pos

    def _parse_main_block(self, hdata: bytes, pos: int, common_args: CommonArgs) -> Rar5MainInfo:
        main_flags, pos = load_vint(hdata, pos)
        main_volume_number = None
        if main_flags & RAR5_MAIN_FLAG_HAS_VOLNR:
            main_volume_number, pos = load_vint(hdata, pos)

        flags = common_args.get("flags", 0) | RAR_MAIN_NEWNUMBERING
        if main_flags & RAR5_MAIN_FLAG_SOLID:
            flags |= RAR_MAIN_SOLID
        if main_flags & RAR5_MAIN_FLAG_ISVOL:
            flags |= RAR_MAIN_VOLUME
        if main_flags & RAR5_MAIN_FLAG_RECOVERY:
            flags |= RAR_MAIN_RECOVERY
        if self._hdrenc_main:
            flags |= RAR_MAIN_PASSWORD
        if main_flags & RAR5_MAIN_FLAG_HAS_VOLNR == 0:
            flags |= RAR_MAIN_FIRSTVOLUME
        common_args["flags"] = flags

        return Rar5MainInfo(main_flags=main_flags,
                            main_volume_number=main_volume_number, **common_args)

    def _parse_file_block(self, hdata: bytes, pos: int, common_args: CommonArgs,
                          cls: type[Rar5BaseFile]) -> Rar5BaseFile:
        block_type = common_args.get("block_type") or 0
        block_flags = common_args.get("block_flags") or 0
        block_extra_size = common_args.get("block_extra_size", 0)

        file_flags, pos = load_vint(hdata, pos)
        file_size, pos = load_vint(hdata, pos)
        mode, pos = load_vint(hdata, pos)

        mtime = None
        if file_flags & RAR5_FILE_FLAG_HAS_MTIME:
            mtime, pos = load_unixtime(hdata, pos)
        crc = None
        if file_flags & RAR5_FILE_FLAG_HAS_CRC32:
            crc, pos = load_le32(hdata, pos)

        file_compress_flags, pos = load_vint(hdata, pos)
        file_host_os, pos = load_vint(hdata, pos)

        name, pos = load_vstr(hdata, pos)
        nul = name.find(b"\0")
        if nul >= 0:
            name = name[:nul]

        # use compatible values
        host_os = RAR_OS_WIN32 if file_host_os == RAR5_OS_WINDOWS else RAR_OS_UNIX

        file_args: InfoArgs = {
            "flags": common_args["flags"],
            "header_crc": common_args["header_crc"],
            "header_size": common_args["header_size"],
            "header_offset": common_args["header_offset"],
            "data_offset": common_args["data_offset"],
            "add_size": common_args["add_size"],
            "block_type": block_type,
            "block_flags": block_flags,
            "block_extra_size": block_extra_size,
            "extract_version": 50,
            "compress_size": common_args["add_size"],
            "file_size": file_size,
            "mode": mode,
            "host_os": host_os,
            "compress_type": RAR_M0 + ((file_compress_flags >> 7) & 7),
            "orig_filename": name,
            "filename": name.decode("utf8", "replace").rstrip("/"),
        }
        if mtime is not None:
            file_args["mtime"] = mtime
            file_args["date_time"] = mtime.timetuple()[:6]
        if crc is not None:
            file_args["CRC"] = crc
            file_args["_md_class"] = CRC32Context
            file_args["_md_expect"] = crc

        file_encryption: FileEncryption = (0, 0, 0, b"", b"", b"")
        flags = common_args["flags"]
        if block_extra_size:
            # allow 1 byte of garbage
            while pos < len(hdata) - 1:
                xsize, pos = load_vint(hdata, pos)
                xdata, pos = load_bytes(hdata, xsize, pos)
                file_encryption, flags = self._process_file_extra(file_args, file_encryption, flags, xdata)

        if block_flags & RAR5_BLOCK_FLAG_SPLIT_BEFORE:
            flags |= RAR_FILE_SPLIT_BEFORE
        if block_flags & RAR5_BLOCK_FLAG_SPLIT_AFTER:
            flags |= RAR_FILE_SPLIT_AFTER
        if file_flags & RAR5_FILE_FLAG_ISDIR:
            flags |= RAR_FILE_DIRECTORY
        if file_compress_flags & RAR5_COMPR_SOLID:
            flags |= RAR_FILE_SOLID
        file_args["flags"] = flags

        h = cls(file_flags=file_flags, file_encryption=file_encryption,
                file_compress_flags=file_compress_flags, file_host_os=file_host_os, **file_args)
        if h.is_dir():
            h.filename = h.filename + "/"
        return h

    def _parse_endarc_block(self, hdata: bytes, pos: int, common_args: CommonArgs) -> Rar5EndArcInfo:
        endarc_flags, pos = load_vint(hdata, pos)
        if endarc_flags & RAR5_ENDARC_FLAG_NEXT_VOL:
            common_args["flags"] = common_args.get("flags", 0) | RAR_ENDARC_NEXT_VOLUME
        return Rar5EndArcInfo(endarc_flags=endarc_flags, **common_args)

    def _check_password(self, check_value: bytes, kdf_count_shift: int, salt: bytes) -> None:
        if len(check_value) != RAR5_PW_CHECK_SIZE + RAR5_PW_SUM_SIZE:
            return
        if kdf_count_shift > RAR_MAX_KDF_SHIFT:
            raise BadRarFile("Too large kdf_count")

        hdr_check = check_value[:RAR5_PW_CHECK_SIZE]
        hdr_sum = check_value[RAR5_PW_CHECK_SIZE:]
        sum_hash = sha256(hdr_check).digest()
        if sum_hash[:RAR5_PW_SUM_SIZE] != hdr_sum:
            return

        kdf_count = (1 << kdf_count_shift) + 32
        pwd = self._get_utf8_password()
        pwd_hash = rar5_s2k(pwd, salt, kdf_count)

        pwd_check = bytearray(RAR5_PW_CHECK_SIZE)
        len_mask = RAR5_PW_CHECK_SIZE - 1
        for i, v in enumerate(pwd_hash):
            pwd_check[i & len_mask] ^= v

        if pwd_check != hdr_check:
            raise RarWrongPassword()

    def _parse_encryption_block(self, hdata: bytes, pos: int, common_args: CommonArgs) -> Rar5EncryptionInfo:
        self._needs_password = True
        encryption_algo, pos = load_vint(hdata, pos)
        encryption_flags, pos = load_vint(hdata, pos)
        encryption_kdf_count, pos = load_byte(hdata, pos)
        encryption_salt, pos = load_bytes(hdata, 16, pos)
        encryption_check_value = None
        if encryption_flags & RAR5_ENC_FLAG_HAS_CHECKVAL:
            encryption_check_value, pos = load_bytes(hdata, 12, pos)
        if encryption_algo != RAR5_XENC_CIPHER_AES256:
            raise BadRarFile("Unsupported header encryption cipher")

        h = Rar5EncryptionInfo(
            encryption_algo=encryption_algo, encryption_flags=encryption_flags,
            encryption_kdf_count=encryption_kdf_count, encryption_salt=encryption_salt,
            encryption_check_value=encryption_check_value, **common_args)
        self._hdrenc_main = h
        if encryption_check_value and self._password:
            self._check_password(encryption_check_value, encryption_kdf_count, encryption_salt)
        return h

    def _process_file_extra(self, file_args: InfoArgs,
                            file_encryption: FileEncryption,
                            flags: int, xdata: bytes
                            ) -> tuple[FileEncryption, int]:
        xtype, pos = load_vint(xdata, 0)
        if xtype == RAR5_XFILE_TIME:
            self._parse_file_xtime(file_args, xdata, pos)
        elif xtype == RAR5_XFILE_ENCRYPTION:
            file_encryption, flags = self._parse_file_encryption(file_args, flags, xdata, pos)
        elif xtype == RAR5_XFILE_HASH:
            self._parse_file_hash(file_args, file_encryption, xdata, pos)
        elif xtype == RAR5_XFILE_VERSION:
            self._parse_file_version(file_args, xdata, pos)
        elif xtype == RAR5_XFILE_REDIR:
            self._parse_file_redir(file_args, xdata, pos)
        elif xtype == RAR5_XFILE_OWNER:
            self._parse_file_owner(file_args, xdata, pos)
        elif xtype == RAR5_XFILE_SERVICE:
            pass
        else:
            pass
        return file_encryption, flags

    # extra block for file time record
    def _parse_file_xtime(self, file_args: InfoArgs, xdata: bytes, pos: int) -> None:
        tflags, pos = load_vint(xdata, pos)

        ldr = load_windowstime
        if tflags & RAR5_XTIME_UNIXTIME:
            ldr = load_unixtime

        mtime: datetime | None = None
        ctime: datetime | None = None
        atime: datetime | None = None
        if tflags & RAR5_XTIME_HAS_MTIME:
            mtime, pos = ldr(xdata, pos)
            file_args["date_time"] = mtime.timetuple()[:6]
        if tflags & RAR5_XTIME_HAS_CTIME:
            ctime, pos = ldr(xdata, pos)
        if tflags & RAR5_XTIME_HAS_ATIME:
            atime, pos = ldr(xdata, pos)

        if tflags & RAR5_XTIME_UNIXTIME_NS:
            if tflags & RAR5_XTIME_HAS_MTIME:
                nsec, pos = load_le32(xdata, pos)
                assert mtime is not None
                mtime = to_nsdatetime(mtime, nsec)
            if tflags & RAR5_XTIME_HAS_CTIME:
                nsec, pos = load_le32(xdata, pos)
                assert ctime is not None
                ctime = to_nsdatetime(ctime, nsec)
            if tflags & RAR5_XTIME_HAS_ATIME:
                nsec, pos = load_le32(xdata, pos)
                assert atime is not None
                atime = to_nsdatetime(atime, nsec)

        if mtime is not None:
            file_args["mtime"] = mtime
        if ctime is not None:
            file_args["ctime"] = ctime
        if atime is not None:
            file_args["atime"] = atime

    # just remember encryption info
    def _parse_file_encryption(self, file_args: InfoArgs, flags: int, xdata: bytes, pos: int
                               ) -> tuple[FileEncryption, int]:
        algo, pos = load_vint(xdata, pos)
        enc_flags, pos = load_vint(xdata, pos)
        kdf_count, pos = load_byte(xdata, pos)
        salt, pos = load_bytes(xdata, 16, pos)
        iv, pos = load_bytes(xdata, 16, pos)
        checkval = None
        if enc_flags & RAR5_XENC_CHECKVAL:
            checkval, pos = load_bytes(xdata, 12, pos)
        if enc_flags & RAR5_XENC_TWEAKED:
            file_args["_md_expect"] = None
            file_args["_md_class"] = NoHashContext

        file_encryption = (algo, enc_flags, kdf_count, salt, iv, checkval)
        flags |= RAR_FILE_PASSWORD
        return file_encryption, flags

    def _parse_file_hash(self, file_args: InfoArgs,
                         file_encryption: FileEncryption,
                         xdata: bytes, pos: int) -> None:
        hash_type, pos = load_vint(xdata, pos)
        if hash_type == RAR5_XHASH_BLAKE2SP:
            blake2sp_hash, pos = load_bytes(xdata, 32, pos)
            file_args["blake2sp_hash"] = blake2sp_hash
            if (file_encryption[1] & RAR5_XENC_TWEAKED) == 0:
                file_args["_md_class"] = Blake2SP
                file_args["_md_expect"] = blake2sp_hash

    def _parse_file_version(self, file_args: InfoArgs, xdata: bytes, pos: int) -> None:
        ver_flags, pos = load_vint(xdata, pos)
        version, pos = load_vint(xdata, pos)
        file_args["file_version"] = (ver_flags, version)

    def _parse_file_redir(self, file_args: InfoArgs, xdata: bytes, pos: int) -> None:
        redir_type, pos = load_vint(xdata, pos)
        redir_flags, pos = load_vint(xdata, pos)
        redir_name_b, pos = load_vstr(xdata, pos)
        redir_name = redir_name_b.decode("utf8", "replace")
        file_args["file_redir"] = (redir_type, redir_flags, redir_name)

    def _parse_file_owner(self, file_args: InfoArgs, xdata: bytes, pos: int) -> None:
        user_name: bytes | None = None
        group_name: bytes | None = None
        user_id: int | None = None
        group_id: int | None = None

        owner_flags, pos = load_vint(xdata, pos)
        if owner_flags & RAR5_XOWNER_UNAME:
            user_name, pos = load_vstr(xdata, pos)
        if owner_flags & RAR5_XOWNER_GNAME:
            group_name, pos = load_vstr(xdata, pos)
        if owner_flags & RAR5_XOWNER_UID:
            user_id, pos = load_vint(xdata, pos)
        if owner_flags & RAR5_XOWNER_GID:
            group_id, pos = load_vint(xdata, pos)

        file_args["file_owner"] = (user_name, group_name, user_id, group_id)

    def process_entry(self, fd: XFile, item: RarEntry) -> None:
        if item.block_type == RAR5_BLOCK_FILE:
            assert isinstance(item, Rar5BaseFile)
            assert item.block_flags is not None
            if item.file_version:
                pass    # skip old versions
            elif (item.block_flags & RAR5_BLOCK_FLAG_SPLIT_BEFORE) == 0:
                # use only first part
                self._info_map[item.filename.rstrip("/")] = item
                self._info_list.append(item)
            elif len(self._info_list) > 0:
                # final crc is in last block
                old = self._info_list[-1]
                old.CRC = item.CRC
                old._md_expect = item._md_expect
                old.blake2sp_hash = item.blake2sp_hash
                assert old.compress_size is not None and item.compress_size is not None
                old.compress_size += item.compress_size
        elif item.block_type == RAR5_BLOCK_SERVICE:
            assert isinstance(item, Rar5BaseFile)
            if item.filename == "CMT":
                self._load_comment(fd, item)

    def _load_comment(self, fd: XFile, item: Rar5BaseFile) -> None:
        assert item.block_flags is not None
        assert item.compress_size is not None
        if item.block_flags & (RAR5_BLOCK_FLAG_SPLIT_BEFORE | RAR5_BLOCK_FLAG_SPLIT_AFTER):
            return None
        if item.compress_type != RAR_M0:
            return None
        if item.compress_size > RAR_MAX_COMMENT:
            return None
        if item.file_size > RAR_MAX_COMMENT:
            return None

        if item.flags & RAR_FILE_PASSWORD:
            algo, ___flags, kdf_count, salt, iv, ___checkval = item.file_encryption
            if algo != RAR5_XENC_CIPHER_AES256:
                return None
            key = self._gen_key(kdf_count, salt)
            f = HeaderDecrypt(fd, key, iv)
            cmt = f.read(item.file_size)
        else:
            # archive comment
            with self._open_clear(item) as cmtstream:
                cmt = cmtstream.read()

        # rar bug? - appends zero to comment
        cmt = cmt.split(b"\0", 1)[0]
        self.comment = cmt.decode("utf8")
        return None

    def _open_hack(self, inf: RarInfo, pwd: str | None) -> RarExtFile:
        # len, type, blk_flags, flags
        main_hdr = b"\x03\x01\x00\x00"
        endarc_hdr = b"\x03\x05\x00\x00"
        main_hdr = S_LONG.pack(crc32(main_hdr)) + main_hdr
        endarc_hdr = S_LONG.pack(crc32(endarc_hdr)) + endarc_hdr
        return self._open_hack_core(inf, pwd, RAR5_ID + main_hdr, endarc_hdr)


##
## Utility functions
##

# number formats
S_LONG = Struct("<L")
S_SHORT = Struct("<H")
S_BYTE = Struct("<B")

# structure formats
S_BLK_HDR = Struct("<HBHH")
S_FILE_HDR = Struct("<LLBLLBBHL")
S_COMMENT_HDR = Struct("<HBBH")
S_OLD_SUBBLOCK_HDR = Struct("<HB")


def load_vint(buf: bytes, pos: int) -> tuple[int, int]:
    """Load RAR5 variable-size int."""
    limit = min(pos + 11, len(buf))
    res = ofs = 0
    while pos < limit:
        b = buf[pos]
        res += ((b & 0x7F) << ofs)
        pos += 1
        ofs += 7
        if b < 0x80:
            return res, pos
    raise BadRarFile("cannot load vint")


def load_byte(buf: bytes, pos: int) -> tuple[int, int]:
    """Load single byte"""
    end = pos + 1
    if end > len(buf):
        raise BadRarFile("cannot load byte")
    return S_BYTE.unpack_from(buf, pos)[0], end


def load_le32(buf: bytes, pos: int) -> tuple[int, int]:
    """Load little-endian 32-bit integer"""
    end = pos + 4
    if end > len(buf):
        raise BadRarFile("cannot load le32")
    return S_LONG.unpack_from(buf, pos)[0], end


def load_bytes(buf: bytes, num: int, pos: int) -> tuple[bytes, int]:
    """Load sequence of bytes"""
    end = pos + num
    if end > len(buf):
        raise BadRarFile("cannot load bytes")
    return buf[pos: end], end


def load_vstr(buf: bytes, pos: int) -> tuple[bytes, int]:
    """Load bytes prefixed by vint length"""
    slen, pos = load_vint(buf, pos)
    return load_bytes(buf, slen, pos)


def load_dostime(buf: bytes, pos: int) -> tuple[datetime, int]:
    """Load LE32 dos timestamp"""
    stamp, pos = load_le32(buf, pos)
    tup = parse_dos_time(stamp)
    return to_datetime(tup), pos


def load_unixtime(buf: bytes, pos: int) -> tuple[datetime, int]:
    """Load LE32 unix timestamp"""
    secs, pos = load_le32(buf, pos)
    dt = datetime.fromtimestamp(secs, timezone.utc)
    return dt, pos


def load_windowstime(buf: bytes, pos: int) -> tuple[datetime, int]:
    """Load LE64 windows timestamp"""
    # unix epoch (1970) in seconds from windows epoch (1601)
    unix_epoch = 11644473600
    val1, pos = load_le32(buf, pos)
    val2, pos = load_le32(buf, pos)
    secs, n1secs = divmod((val2 << 32) | val1, 10000000)
    dt = datetime.fromtimestamp(secs - unix_epoch, timezone.utc)
    dt = to_nsdatetime(dt, n1secs * 100)
    return dt, pos


#
# volume numbering
#

_rc_num = re.compile("^[0-9]+$")


def _next_newvol(volfile: str) -> str:
    """New-style next volume
    """
    name, ext = os.path.splitext(volfile)
    if ext.lower() in ("", ".exe", ".sfx"):
        volfile = name + ".rar"
    i = len(volfile) - 1
    while i >= 0:
        if "0" <= volfile[i] <= "9":
            return _inc_volname(volfile, i, False)
        if volfile[i] in ("/", os.sep):
            break
        i -= 1
    raise BadRarName("Cannot construct volume name: " + volfile)


def _next_oldvol(volfile: str) -> str:
    """Old-style next volume
    """
    name, ext = os.path.splitext(volfile)
    if ext.lower() in ("", ".exe", ".sfx"):
        ext = ".rar"
    sfx = ext[2:]
    if _rc_num.match(sfx):
        ext = _inc_volname(ext, len(ext) - 1, True)
    else:
        # .rar -> .r00
        ext = ext[:2] + "00"
    return name + ext


def _inc_volname(volfile: str, i: int, inc_chars: bool) -> str:
    """increase digits with carry, otherwise just increment char
    """
    fn = list(volfile)
    while i >= 0:
        if fn[i] == "9":
            fn[i] = "0"
            i -= 1
            if i < 0:
                fn.insert(0, "1")
        elif "0" <= fn[i] < "9" or inc_chars:
            fn[i] = chr(ord(fn[i]) + 1)
            break
        else:
            fn.insert(i + 1, "1")
            break
    return "".join(fn)


def _parse_ext_time(file_args: InfoArgs, data: bytes, pos: int) -> int:
    """Parse all RAR3 extended time fields
    """
    # flags and rest of data can be missing
    flags = 0
    if pos + 2 <= len(data):
        flags = S_SHORT.unpack_from(data, pos)[0]
        pos += 2

    mtime, pos = _parse_xtime(flags >> 3 * 4, data, pos, file_args.get("mtime"))
    file_args["ctime"], pos = _parse_xtime(flags >> 2 * 4, data, pos)
    file_args["atime"], pos = _parse_xtime(flags >> 1 * 4, data, pos)
    file_args["arctime"], pos = _parse_xtime(flags >> 0 * 4, data, pos)
    if mtime:
        file_args["mtime"] = mtime
        file_args["date_time"] = mtime.timetuple()[:6]
    return pos


def _parse_xtime(flag: int, data: bytes, pos: int, basetime: datetime | None = None) -> tuple[datetime | None, int]:
    """Parse one RAR3 extended time field
    """
    res = None
    if flag & 8:
        if not basetime:
            basetime, pos = load_dostime(data, pos)

        # load second fractions of 100ns units
        rem = 0
        cnt = flag & 3
        for _ in range(cnt):
            b, pos = load_byte(data, pos)
            rem = (b << 16) | (rem >> 8)

        # dostime has room for 30 seconds only, correct if needed
        if flag & 4 and basetime.second < 59:
            basetime = basetime.replace(second=basetime.second + 1)

        res = to_nsdatetime(basetime, rem * 100)
    return res, pos


def rar3_decompress(vers: int, meth: int, data: bytes, declen: int = 0, flags: int = 0,
                    crc: int = 0, pwd: str | None = None, salt: bytes | None = None) -> bytes:
    """Decompress blob of compressed data.

    Used for data with non-standard header - eg. comments.
    """
    # already uncompressed?
    if meth == RAR_M0 and (flags & RAR_FILE_PASSWORD) == 0:
        return data

    # take only necessary flags
    flags = flags & (RAR_FILE_PASSWORD | RAR_FILE_SALT | RAR_FILE_DICTMASK)
    flags |= RAR_LONG_BLOCK

    # file header
    fname = b"data"
    date = ((2010 - 1980) << 25) + (12 << 21) + (31 << 16)
    mode = DOS_MODE_ARCHIVE
    fhdr = S_FILE_HDR.pack(len(data), declen, RAR_OS_MSDOS, crc,
                           date, vers, meth, len(fname), mode)
    fhdr += fname
    if salt:
        fhdr += salt

    # full header
    hlen = S_BLK_HDR.size + len(fhdr)
    hdr = S_BLK_HDR.pack(0, RAR_BLOCK_FILE, flags, hlen) + fhdr
    hcrc = crc32(hdr[2:]) & 0xFFFF
    hdr = S_BLK_HDR.pack(hcrc, RAR_BLOCK_FILE, flags, hlen) + fhdr

    # archive main header
    mh = S_BLK_HDR.pack(0x90CF, RAR_BLOCK_MAIN, 0, 13) + b"\0" * (2 + 4)

    # decompress via temp rar
    setup = tool_setup()
    tmpfd, tmpname = mkstemp(suffix=".rar", dir=config.HACK_TMP_DIR)
    tmpf = os.fdopen(tmpfd, "wb")
    try:
        tmpf.write(RAR_ID + mh + hdr + data)
        tmpf.close()

        curpwd = (flags & RAR_FILE_PASSWORD) and pwd or None
        cmd = setup.open_cmdline(curpwd, tmpname)
        p = custom_popen(cmd)
        return p.communicate()[0]
    finally:
        tmpf.close()
        os.unlink(tmpname)
