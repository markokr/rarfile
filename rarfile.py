# rarfile.py
#
# Copyright (c) 2005-2010  Marko Kreen <markokr@gmail.com>
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

"""RAR archive reader.

This is Python module for Rar archive reading.  The interface
is made as zipfile like as possible.

Basic logic:
 - Parse archive structure with Python.
 - Extract non-compressed files with Python
 - Extract compressed files with unrar.
 - Optionally write compressed data to temp file to speed up unrar,
   otherwise it needs to scan whole archive on each execution.
"""

__version__ = '2.2'

import sys, os
from struct import pack, unpack
from binascii import crc32
from tempfile import mkstemp
from subprocess import Popen, PIPE, STDOUT

# only needed for encryped headers
try:
    from Crypto.Cipher import AES
    from hashlib import sha1
    _have_crypto = 1
except ImportError:
    _have_crypto = 0

# export only interesting items
__all__ = ['is_rarfile', 'RarInfo', 'RarFile']

##
## Module configuration.  Can be tuned after importing.
##

# default fallback charset
DEFAULT_CHARSET = "windows-1252"

# 'unrar', 'rar' or full path to either one
UNRAR_TOOL = "unrar"

# For some reason 'unrar' does not have 'cw' comment.  Use 'rar' here then.
# Can be full path, or None to disable
COMMENT_TOOL = "rar"

# Command line args to use for opening file for reading.
OPEN_ARGS = ('p', '-inul')

# Command line args to use for extracting file to disk.
EXTRACT_ARGS = ('x', '-y', '-idq')

# how to extract comment from archive.  (rar, tmpfile) will be added.
COMMENT_ARGS = ('cw', '-y', '-inul', '-p-')

# args for testrar()
TEST_ARGS = ('t', '-idq')

# whether to speed up decompression by using tmp archive
USE_EXTRACT_HACK = 1

# limit the filesize for tmp archive usage
HACK_SIZE_LIMIT = 20*1024*1024

##
## rar constants
##

# block types
RAR_BLOCK_MARK          = 0x72 # r
RAR_BLOCK_MAIN          = 0x73 # s
RAR_BLOCK_FILE          = 0x74 # t
RAR_BLOCK_OLD_COMMENT   = 0x75 # u
RAR_BLOCK_OLD_EXTRA     = 0x76 # v
RAR_BLOCK_OLD_SUB       = 0x77 # w
RAR_BLOCK_OLD_RECOVERY  = 0x78 # x
RAR_BLOCK_OLD_AUTH      = 0x79 # y
RAR_BLOCK_SUB           = 0x7a # z
RAR_BLOCK_ENDARC        = 0x7b # {

# flags for RAR_BLOCK_MAIN
RAR_MAIN_VOLUME         = 0x0001
RAR_MAIN_COMMENT        = 0x0002
RAR_MAIN_LOCK           = 0x0004
RAR_MAIN_SOLID          = 0x0008
RAR_MAIN_NEWNUMBERING   = 0x0010
RAR_MAIN_AUTH           = 0x0020
RAR_MAIN_RECOVERY       = 0x0040
RAR_MAIN_PASSWORD       = 0x0080
RAR_MAIN_FIRSTVOLUME    = 0x0100
RAR_MAIN_ENCRYPTVER     = 0x0200

# flags for RAR_BLOCK_FILE
RAR_FILE_SPLIT_BEFORE   = 0x0001
RAR_FILE_SPLIT_AFTER    = 0x0002
RAR_FILE_PASSWORD       = 0x0004
RAR_FILE_COMMENT        = 0x0008
RAR_FILE_SOLID          = 0x0010
RAR_FILE_DICTMASK       = 0x00e0
RAR_FILE_DICT64         = 0x0000
RAR_FILE_DICT128        = 0x0020
RAR_FILE_DICT256        = 0x0040
RAR_FILE_DICT512        = 0x0060
RAR_FILE_DICT1024       = 0x0080
RAR_FILE_DICT2048       = 0x00a0
RAR_FILE_DICT4096       = 0x00c0
RAR_FILE_DIRECTORY      = 0x00e0
RAR_FILE_LARGE          = 0x0100
RAR_FILE_UNICODE        = 0x0200
RAR_FILE_SALT           = 0x0400
RAR_FILE_VERSION        = 0x0800
RAR_FILE_EXTTIME        = 0x1000
RAR_FILE_EXTFLAGS       = 0x2000

# flags for RAR_BLOCK_ENDARC
RAR_ENDARC_NEXT_VOLUME  = 0x0001
RAR_ENDARC_DATACRC      = 0x0002
RAR_ENDARC_REVSPACE     = 0x0004
RAR_ENDARC_VOLNR        = 0x0008

# flags common to all blocks
RAR_SKIP_IF_UNKNOWN     = 0x4000
RAR_LONG_BLOCK          = 0x8000

# Host OS types
RAR_OS_MSDOS = 0
RAR_OS_OS2   = 1
RAR_OS_WIN32 = 2
RAR_OS_UNIX  = 3
RAR_OS_MACOS = 4
RAR_OS_BEOS  = 5

##
## Compatibility code to support both python 2 and 3
##

# compat with 2.x
if sys.hexversion < 0x3000000:
    # prefer 3.x behaviour
    range = xrange
    # py2.6 has broken bytes()
    def bytes(foo, enc):
        return str(foo)

# see if compat bytearray() is needed
try:
    bytearray()
except NameError:
    import array
    class bytearray:
        def __init__(self, val = ''):
            self.arr = array.array('B', val)
            self.append = self.arr.append
            self.__getitem__ = self.arr.__getitem__
            self.__len__ = self.arr.__len__
        def decode(self, *args):
            return self.arr.tostring().decode(*args)

# Struct() for older python
try:
    from struct import Struct
except ImportError:
    from struct import calcsize
    class Struct:
        def __init__(self, fmt):
            self.format = fmt
            self.size = calcsize(fmt)
        def unpack(self, buf):
            return unpack(self.format, buf)
        def unpack_from(self, buf, ofs = 0):
            return unpack(self.format, buf[ofs : ofs + self.size])
        def pack(self, *args):
            return pack(self.format, *args)

# for python 2.3
try:
    DEVNULL = os.devnull
except AttributeError:
    DEVNULL = '/dev/null'

# internal byte constants
RAR_ID = bytes("Rar!\x1a\x07\x00", 'ascii')
ZERO = bytes("\0", 'ascii')
EMPTY = bytes("", 'ascii')

# Struct() constants
S_BLK_HDR = Struct('<HBHH')
S_FILE_HDR = Struct('<LLBLLBBHL')
S_LONG = Struct('<L')
S_SHORT = Struct('<H')
S_BYTE = Struct('<B')

# disconnect cmd from parent fds, read only from stdout
def custom_popen(cmd):
    # needed for py2exe
    creationflags = 0
    if sys.platform == 'win32':
        creationflags = 0x08000000 # CREATE_NO_WINDOW

    # 3xPIPE seems unreliable, at least on osx
    try:
        null = open(DEVNULL, "wb")
        _in = null
        _err = null
    except IOError:
        _in = PIPE
        _err = STDOUT

    # run command
    return Popen(cmd, stdout = PIPE, stdin = _in, stderr = _err, creationflags = creationflags)

#
# Public interface
#

class Error(Exception):
    """Base class for rarfile errors."""
class BadRarFile(Error):
    """Incorrect data in archive."""
class NotRarFile(Error):
    """The file is not RAR archive."""
class BadRarName(Error):
    """Cannot guess multipart name components."""
class NoRarEntry(Error):
    """File not found in RAR"""
class PasswordRequired(Error):
    """File requires password"""
class NeedFirstVolume(Error):
    """Need to start from first volume."""
class NoCrypto(Error):
    """Cannot parse encrypted headers - no crypto available."""

def is_rarfile(fn):
    '''Check quickly whether file is rar archive.'''
    buf = open(fn, "rb").read(len(RAR_ID))
    return buf == RAR_ID

class RarInfo(object):
    '''An entry in rar archive.
    
    @ivar filename:
        File name with relative path.
        Note that Rar uses "\\" as directory separator.
        Always unicode string.
    @ivar date_time:
        Modification time, tuple of (year, month, day, hour, minute, second).
    @ivar file_size:
        Uncompressed size.
    @ivar compress_size:
        Compressed size.
    @ivar compress_type:
        Compression method: 0x30 - 0x35.
    @ivar extract_version:
        Minimal Rar version needed for decompressing.
    @ivar host_os:
        Host OS type, one of RAR_OS_* constants.
    @ivar mode:
        File attributes. May be either dos-style or unix-style, depending on host_os.
    @ivar CRC:
        CRC-32 of uncompressed file, unsigned int.
    @ivar volume:
        Volume nr, starting from 0.
    @ivar volume_file:
        Volume file name, where file starts.
    @ivar type:
        One of RAR_BLOCK_* types.  Only entries with type==RAR_BLOCK_FILE are shown in .infolist().
    @ivar flags:
        For files, RAR_FILE_* bits.
    @ivar orig_filename:
        Byte string of non-unicode representation.

    @ivar mtime:
        Optional time field: Modification time, tuple of (year, month, day, hour, minute, second).
    @ivar ctime:
        Optional time field: creation time.
    @ivar atime:
        Optional time field: last access time.
    @ivar arctime:
        Optional time field: archival time.

    @ivar unicode_filename:
        Obsolete: same as .filename
    '''

    __slots__ = (
        'compress_size',
        'file_size',
        'host_os',
        'CRC',
        'extract_version',
        'compress_type',
        'mode',
        'type',
        'flags',
        'volume',
        'filename',
        'orig_filename',
        'date_time',

        # optional extended time fields
        # same format as date_time, but sec is float
        'mtime',
        'ctime',
        'atime',
        'arctime',

        # obsolete
        'unicode_filename',

        # RAR internals
        'name_size',
        'header_size',
        'header_crc',
        'file_offset',
        'add_size',
        'header_data',
        'header_unknown',
        'header_offset',
        'salt',
        'volume_file',
    )

    def isdir(self):
        '''Returns True if the entry is a directory.'''
        if self.type == RAR_BLOCK_FILE:
            return (self.flags & RAR_FILE_DIRECTORY) == RAR_FILE_DIRECTORY
        return False

    def needs_password(self):
        return self.flags & RAR_FILE_PASSWORD

class RarFile(object):
    '''Rar archive handling.'''
    def __init__(self, rarfile, mode="r", charset=None, info_callback=None, crc_check = True):
        """Open and parse a RAR archive.
        
        @param rarfile: archive file name
        @param mode: only 'r' is supported.
        @param charset: fallback charset to use, if filenames are not already Unicode-enabled.
        @param info_callback: debug callback, gets to see all archive entries.
        @param crc_check: set to False to disable CRC checks
        """
        self.rarfile = rarfile
        self._charset = charset or DEFAULT_CHARSET
        self._info_callback = info_callback

        self._info_list = []
        self._needs_password = False
        self._password = None
        self._crc_check = crc_check
        self._has_comment = False

        self._main = None

        if mode != "r":
            raise NotImplementedError("RarFile supports only mode=r")

        self._parse()

    def __getattr__(self, name):
        '''Lazy extraction of archive comment.'''
        if name == 'comment':
            cmt = None
            if self._has_comment:
                cmt = self._read_comment()
            self.comment = cmt
            return cmt
        raise AttributeError(name)

    def setpassword(self, password):
        '''Sets the password to use when extracting.'''
        self._password = password
        if not self._main:
            self._parse()

    def needs_password(self):
        '''Returns True if any archive entries require password for extraction.'''
        return self._needs_password

    def namelist(self):
        '''Return list of filenames in archive.'''
        res = []
        for f in self._info_list:
            res.append(f.filename)
        return res

    def infolist(self):
        '''Return RarInfo objects for all files/directories in archive.'''
        return self._info_list

    def getinfo(self, fname):
        '''Return RarInfo for file.'''

        if isinstance(fname, RarInfo):
            return fname

        fname2 = fname.replace("/", "\\")
        for f in self._info_list:
            if fname == f.filename or fname2 == f.filename:
                return f
        raise NoRarEntry("No such file: "+fname)

    def open(self, fname, mode = 'r', psw = None):
        '''Return open file object, where the data can be read.
        
        The object has only .read() and .close() methods.

        @param fname: file name or RarInfo instance.
        @param mode: must be 'r'
        @param psw: password to use for extracting.
        '''

        if mode != 'r':
            raise NotImplementedError("RarFile.open() supports only mode=r")

        # entry lookup
        inf = self.getinfo(fname)
        if inf.isdir():
            raise TypeError("Directory does not have any data: " + inf.filename)

        if inf.flags & RAR_FILE_SPLIT_BEFORE:
            raise NeedFirstVolume("Partial file, please start from first volume: " + inf.filename)

        # check password
        if inf.needs_password():
            psw = psw or self._password
            if psw is None:
                raise PasswordRequired("File %s requires password" % inf.filename)
        else:
            psw = None

        # is temp write usable?
        skip_hack = self._main.flags & (RAR_MAIN_SOLID | RAR_MAIN_VOLUME | RAR_MAIN_PASSWORD)

        if inf.compress_type == 0x30 and psw is None:
            return self._open_clear(inf)
        elif USE_EXTRACT_HACK and not skip_hack and inf.file_size <= HACK_SIZE_LIMIT:
            return self._open_hack(inf, psw)
        else:
            return self._open_unrar(self.rarfile, inf, psw)

    def read(self, fname, psw = None):
        """Return uncompressed data for archive entry.
        
        For longer files using .open() may be better idea.

        @param fname: filename or RarInfo instance
        @param psw: password to use for extracting.
        """

        f = self.open(fname, 'r', psw)
        data = f.read()
        f.close()
        return data

    def close(self):
        """Release open resources."""
        pass

    def printdir(self):
        """Print archive file list to stdout."""
        for f in self._info_list:
            print(f.filename)

    def extract(self, member, path=None, pwd=None):
        """Extract single file into current directory.
        
        @param member: filename or RarInfo instance
        @param path: optional destination path
        @param pwd: optional password to use
        """
        if isinstance(member, RarInfo):
            fname = member.filename
        else:
            fname = member
        self._extract([fname], path, pwd)

    def extractall(self, path=None, members=None, pwd=None):
        """Extract all files into current directory.
        
        @param path: optional destination path
        @param members: optional filename or RarInfo instance list to extract
        @param pwd: optional password to use
        """
        fnlist = []
        if members is not None:
            for m in members:
                if isinstance(m, RarInfo):
                    fnlist.append(m.filename)
                else:
                    fnlist.append(m)
        self._extract(fnlist, path, pwd)

    def testrar(self):
        """Let 'unrar' test the archive.
        """
        cmd = [UNRAR_TOOL] + list(TEST_ARGS)
        if self._password is not None:
            cmd.append('-p' + self._password)
        else:
            cmd.append('-p-')
        cmd.append(self.rarfile)
        p = custom_popen(cmd)
        if p.wait() != 0:
            raise BadRarFile("Testing failed")

    ##
    ## private methods
    ##

    # store entry
    def _process_entry(self, item):
        if item.type == RAR_BLOCK_FILE:
            # use only first part
            if (item.flags & RAR_FILE_SPLIT_BEFORE) == 0:
                self._info_list.append(item)
                # remember if any items require password
                if item.needs_password():
                    self._needs_password = True
            elif len(self._info_list) > 0:
                # final crc is in last block
                old = self._info_list[-1]
                old.CRC = item.CRC
                old.compress_size += item.compress_size

        if self._info_callback:
            self._info_callback(item)

    # read rar
    def _parse(self):
        fd = open(self.rarfile, "rb")
        id = fd.read(len(RAR_ID))
        if id != RAR_ID:
            raise NotRarFile("Not a Rar archive: "+self.rarfile)

        volume = 0  # first vol (.rar) is 0
        more_vols = 0
        endarc = 0
        volfile = self.rarfile
        while 1:
            if endarc:
                h = None    # don't read past ENDARC
            else:
                h = self._parse_header(fd)
            if not h:
                if more_vols:
                    volume += 1
                    volfile = self._next_volname(volfile)
                    fd = open(volfile, "rb")
                    more_vols = 0
                    endarc = 0
                    if fd:
                        continue
                break
            h.volume = volume
            h.volume_file = volfile

            if h.type == RAR_BLOCK_MAIN and not self._main:
                self._main = h
                if h.flags & RAR_MAIN_NEWNUMBERING:
                    # RAR 2.x does not set FIRSTVOLUME,
                    # so check it only if NEWNUMBERING is used
                    if (h.flags & RAR_MAIN_FIRSTVOLUME) == 0:
                        raise NeedFirstVolume("Need to start from first volume")
                if h.flags & RAR_MAIN_COMMENT:
                    self._has_comment = True
                if h.flags & RAR_MAIN_PASSWORD:
                    self._needs_password = True
                    if not self._password:
                        self._main = None
                        break
            elif h.type == RAR_BLOCK_ENDARC:
                more_vols = h.flags & RAR_ENDARC_NEXT_VOLUME
                endarc = 1
            elif h.type == RAR_BLOCK_FILE:
                # RAR 2.x does not write RAR_BLOCK_ENDARC
                if h.flags & RAR_FILE_SPLIT_AFTER:
                    more_vols = 1
                # RAR 2.x does not set RAR_MAIN_FIRSTVOLUME
                if volume == 0 and h.flags & RAR_FILE_SPLIT_BEFORE:
                    raise NeedFirstVolume("Need to start from first volume")
            elif h.type == RAR_BLOCK_SUB:
                # CMT, RR
                if h.filename == 'CMT':
                    self._has_comment = True

            # store it
            self._process_entry(h)

            # go to next header
            if h.add_size > 0:
                fd.seek(h.file_offset + h.add_size, 0)
        fd.close()

    # AES encrypted headers
    _last_aes_key = (None, None, None) # (salt, key, iv)
    def _decrypt_header(self, fd):
        if not _have_crypto:
            raise NoCrypto('Cannot parse encrypted headers - no crypto')
        salt = fd.read(8)
        if self._last_aes_key[0] == salt:
            key, iv = self._last_aes_key[1:]
        else:
            key, iv = rar3_s2k(self._password, salt)
            self._last_aes_key = (salt, key, iv)
        return HeaderDecrypt(fd, key, iv)

    # read single header
    def _parse_header(self, fd):
        # handle encrypted headers
        if self._main and self._main.flags & RAR_MAIN_PASSWORD:
            if not self._password:
                return
            fd = self._decrypt_header(fd)

        # now read actual header
        h = self._parse_block_header(fd)
        if h and (h.type == RAR_BLOCK_FILE or h.type == RAR_BLOCK_SUB):
            self._parse_file_header(h)
        return h

    # common header
    def _parse_block_header(self, fd):
        h = RarInfo()
        h.header_offset = fd.tell()
        buf = fd.read(S_BLK_HDR.size)
        if not buf:
            return None

        t = S_BLK_HDR.unpack_from(buf)
        h.header_crc, h.type, h.flags, h.header_size = t
        h.header_unknown = h.header_size - S_BLK_HDR.size

        if h.header_size > S_BLK_HDR.size:
            h.header_data = fd.read(h.header_size - S_BLK_HDR.size)
        else:
            h.header_data = EMPTY
        h.file_offset = fd.tell()

        if h.flags & RAR_LONG_BLOCK:
            h.add_size = S_LONG.unpack_from(h.header_data)[0]
        else:
            h.add_size = 0

        # no crc check on that
        if h.type == RAR_BLOCK_MARK:
            return h

        # check crc
        if h.type == RAR_BLOCK_MAIN:
            crcdat = buf[2:] + h.header_data[:6]
        elif h.type == RAR_BLOCK_OLD_AUTH:
            crcdat = buf[2:] + h.header_data[:8]
        elif h.type == RAR_BLOCK_OLD_SUB:
            crcdat = buf[2:] + h.header_data + fd.read(h.add_size)
        else:
            crcdat = buf[2:] + h.header_data

        calc_crc = crc32(crcdat) & 0xFFFF

        # return good header
        if h.header_crc == calc_crc:
            return h

        # instead panicing, send eof
        return None

    # read file-specific header
    def _parse_file_header(self, h):
        fld = S_FILE_HDR.unpack_from(h.header_data)
        h.compress_size = fld[0]
        h.file_size = fld[1]
        h.host_os = fld[2]
        h.CRC = fld[3]
        h.date_time = self._parse_dos_time(fld[4])
        h.extract_version = fld[5]
        h.compress_type = fld[6]
        h.name_size = fld[7]
        h.mode = fld[8]
        pos = S_FILE_HDR.size

        if h.flags & RAR_FILE_LARGE:
            h1 = S_LONG.unpack_from(h.header_data, pos)[0]
            h2 = S_LONG.unpack_from(h.header_data, pos + 4)[0]
            h.compress_size |= h1 << 32
            h.file_size |= h2 << 32
            pos += 8
            h.add_size = h.compress_size

        name = h.header_data[pos : pos + h.name_size ]
        pos += h.name_size
        if h.flags & RAR_FILE_UNICODE:
            nul = name.find(ZERO)
            h.orig_filename = name[:nul]
            u = _UnicodeFilename(h.orig_filename, name[nul + 1 : ])
            h.unicode_filename = u.decode()
        else:
            h.orig_filename = name
            h.unicode_filename = name.decode(self._charset, "replace")

        h.filename = h.unicode_filename

        if h.flags & RAR_FILE_SALT:
            h.salt = h.header_data[pos : pos + 8]
            pos += 8
        else:
            h.salt = None

        # optional extended time stamps
        if h.flags & RAR_FILE_EXTTIME:
            pos = self._parse_ext_time(h, pos)
        else:
            h.mtime = h.atime = h.ctime = h.arctime = None

        # unknown contents
        h.header_unknown -= pos

        return h

    def _parse_dos_time(self, stamp):
        sec = stamp & 0x1F; stamp = stamp >> 5
        min = stamp & 0x3F; stamp = stamp >> 6
        hr  = stamp & 0x1F; stamp = stamp >> 5
        day = stamp & 0x1F; stamp = stamp >> 5
        mon = stamp & 0x0F; stamp = stamp >> 4
        yr = (stamp & 0x7F) + 1980
        return (yr, mon, day, hr, min, sec * 2)

    def _parse_ext_time(self, h, pos):
        data = h.header_data

        # flags and rest of data can be missing
        flags = 0
        if pos + 2 <= len(data):
            flags = S_SHORT.unpack_from(data, pos)[0]
            pos += 2

        h.mtime, pos = self._parse_xtime(flags >> 3*4, data, pos, h.date_time)
        h.ctime, pos = self._parse_xtime(flags >> 2*4, data, pos)
        h.atime, pos = self._parse_xtime(flags >> 1*4, data, pos)
        h.arctime, pos = self._parse_xtime(flags >> 0*4, data, pos)
        return pos

    def _parse_xtime(self, flag, data, pos, dostime = None):
        unit = 10000000.0 # 100 ns units
        if flag & 8:
            if not dostime:
                t = S_LONG.unpack_from(data, pos)[0]
                dostime = self._parse_dos_time(t)
                pos += 4
            rem = 0
            cnt = flag & 3
            for i in range(cnt):
                b = S_BYTE.unpack_from(data, pos)[0]
                rem = (b << 16) | (rem >> 8)
                pos += 1
            sec = dostime[5] + rem / unit
            if flag & 4:
                sec += 1
            dostime = dostime[:5] + (sec,)
        return dostime, pos

    # given current vol name, construct next one
    def _next_volname(self, volfile):
        if self._main.flags & RAR_MAIN_NEWNUMBERING:
            return self._next_newvol(volfile)
        return self._next_oldvol(volfile)

    # new-style next volume
    def _next_newvol(self, volfile):
        i = len(volfile) - 1
        while i >= 0:
            if volfile[i] >= '0' and volfile[i] <= '9':
                return self._inc_volname(volfile, i)
            i -= 1
        raise BadRarName("Cannot construct volume name: "+fn)

    # old-style next volume
    def _next_oldvol(self, volfile):
        # rar -> r00
        if volfile[-4:].lower() == '.rar':
            return volfile[:-2] + '00'
        return self._inc_volname(volfile, len(volfile) - 1)

    # increase digits with carry, otherwise just increment char
    def _inc_volname(self, volfile, i):
        fn = list(volfile)
        while i >= 0:
            if fn[i] != '9':
                fn[i] = chr(ord(fn[i]) + 1)
                break
            fn[i] = '0'
            i -= 1
        return ''.join(fn)

    def _open_clear(self, inf):
        return DirectReader(self, inf)

    # put file compressed data into temporary .rar archive, and run
    # unrar on that, thus avoiding unrar going over whole archive
    def _open_hack(self, inf, psw = None):
        BSIZE = 32*1024

        size = inf.compress_size + inf.header_size
        rf = open(self.rarfile, "rb")
        rf.seek(inf.header_offset)

        tmpfd, tmpname = mkstemp(suffix='.rar')
        tmpf = os.fdopen(tmpfd, "wb")

        try:
            # create main header: crc, type, flags, size, res1, res2
            mh = S_BLK_HDR.pack(0x90CF, 0x73, 0, 13) + ZERO * (2+4)
            tmpf.write(RAR_ID + mh)
            while size > 0:
                if size > BSIZE:
                    buf = rf.read(BSIZE)
                else:
                    buf = rf.read(size)
                if not buf:
                    raise BadRarFile('read failed - broken archive')
                tmpf.write(buf)
                size -= len(buf)
            tmpf.close()
        except:
            os.unlink(tmpname)
            raise

        return self._open_unrar(tmpname, inf, psw, tmpname)

    # extract using unrar
    def _open_unrar(self, rarfile, inf, psw = None, tmpfile = None):
        cmd = [UNRAR_TOOL] + list(OPEN_ARGS)
        if psw is not None:
            cmd.append("-p" + psw)
        cmd.append(rarfile)

        # not giving filename avoids encoding related problems
        if not tmpfile:
            fn = inf.filename
            fn = fn.replace('\\', os.sep)
            cmd.append(fn)

        # read from unrar pipe
        return PipeReader(self, inf, cmd, tmpfile)

    def _read_comment(self):
        if not COMMENT_TOOL:
            return
        tmpfd, tmpname = mkstemp(suffix='.txt')
        comment = None
        try:
            cmd = [COMMENT_TOOL] + list(COMMENT_ARGS)
            cmd.append(self.rarfile)
            cmd.append(tmpname)
            try:
                p = custom_popen(cmd)
                cmt = None
                if p.wait() == 0:
                    cmt = os.fdopen(tmpfd, 'rb').read()
                    try:
                        comment = cmt.decode('utf8')
                    except UnicodeError:
                        comment = cmt.decode(self._charset, 'replace')
            except (OSError, IOError):
                pass
        finally:
            os.unlink(tmpname)

        return comment

    # call unrar to extract a file
    def _extract(self, fnlist, path=None, psw=None):
        cmd = [UNRAR_TOOL] + list(EXTRACT_ARGS)

        # pasoword
        psw = psw or self._password
        if psw is not None:
            cmd.append('-p' + psw)
        else:
            cmd.append('-p-')

        # rar file
        cmd.append(self.rarfile)

        # file list
        cmd += fnlist

        # destination path
        if path is not None:
            cmd.append(path + os.sep)

        # call
        p = custom_popen(cmd)
        p.wait()

# handle unicode filename compression
class _UnicodeFilename:
    def __init__(self, name, encdata):
        self.std_name = bytearray(name)
        self.encdata = bytearray(encdata)
        self.pos = self.encpos = 0
        self.buf = bytearray()

    def enc_byte(self):
        c = self.encdata[self.encpos]
        self.encpos += 1
        return c

    def std_byte(self):
        return self.std_name[self.pos]

    def put(self, lo, hi):
        self.buf.append(lo)
        self.buf.append(hi)
        self.pos += 1

    def decode(self):
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
                    for i in range((n & 0x7f) + 2):
                        lo = (self.std_byte() + c) & 0xFF
                        self.put(lo, hi)
                else:
                    for i in range(n + 2):
                        self.put(self.std_byte(), 0)
        return self.buf.decode("utf-16le", "replace")


class BaseReader:
    """Base class for 'file-like' object that RarFile.open() returns.

    Provides public methods and common crc checking.
    """

    def __init__(self, rf, inf, tempfile = None):
        self.rf = rf
        self.inf = inf
        self.crc_check = rf._crc_check
        self.CRC = 0
        self.remain = inf.file_size
        self.tempfile = tempfile
        self.fd = None

    def read(self, cnt = None):
        """Read all or specified amount of data from archive entry."""

        # sanitize cnt
        if cnt is None:
            cnt = self.remain
        elif cnt > self.remain:
            cnt = self.remain
        if cnt <= 0:
            return EMPTY

        # actual read
        data = self._read(cnt)
        if data:
            self.CRC = crc32(data, self.CRC)
            self.remain -= len(data)

        # done?
        if not data or self.remain == 0:
            self.close()
            self._check()
        return data

    def _check(self):
        """Check final CRC."""
        if not self.crc_check:
            return
        if self.remain != 0:
            raise BadRarFile("Failed the read enough data")
        crc = self.CRC
        if crc < 0:
            crc += (long(1) << 32)
        if crc != self.inf.CRC:
            raise BadRarFile("Corrupt file - CRC check failed")

    def _read(self, cnt):
        """Actual read that gets sanitized cnt."""

    def close(self):
        """Close open resources."""

        if self.fd:
            self.fd.close()
            self.fd = None
        if self.tempfile:
            os.unlink(self.tempfile)
            self.tempfile = None

    def __del__(self):
        """Hook delete to make sure tempfile is removed."""
        self.close()


class PipeReader(BaseReader):
    """Read data from pipe, handle tempfile cleanup."""

    def __init__(self, rf, inf, cmd, tempfile=None):
        BaseReader.__init__(self, rf, inf, tempfile)
        self.proc = custom_popen(cmd)
        self.fd = self.proc.stdout

    def _read(self, cnt):
        """Read from pipe."""
        return self.fd.read(cnt)


class DirectReader(BaseReader):
    """Read uncompressed data directly from archive."""

    def __init__(self, rf, inf):
        BaseReader.__init__(self, rf, inf)
        self.volfile = inf.volume_file
        self.size = inf.file_size

        self.fd = open(self.volfile, "rb")
        self.fd.seek(self.inf.header_offset, 0)
        self.cur = self.rf._parse_header(self.fd)
        self.cur_avail = self.cur.add_size

    def _read(self, cnt):
        """Read from potentially multi-volume archive."""

        buf = EMPTY
        while cnt > 0:
            # next vol needed?
            if self.cur_avail == 0:
                if not self._open_next():
                    break

            # fd is in read pos, do the read
            if cnt > self.cur_avail:
                data = self.fd.read(self.cur_avail)
            else:
                data = self.fd.read(cnt)
            if not data:
                break

            # got some data
            cnt -= len(data)
            self.cur_avail -= len(data)
            if buf:
                buf += data
            else:
                buf = data

        return buf

    def _open_next(self):
        """Proceed to next volume."""

        # is the file split over archives?
        if (self.cur.flags & RAR_FILE_SPLIT_AFTER) == 0:
            return False

        # open next part
        self.volfile = self.rf._next_volname(self.volfile)
        fd = open(self.volfile, "rb")
        self.fd = fd

        # loop until first file header
        while 1:
            cur = self.rf._parse_header(fd)
            if not cur:
                raise BadRarFile("Unexpected EOF")
            if cur.type in (RAR_BLOCK_MARK, RAR_BLOCK_MAIN):
                if cur.add_size:
                    fd.seek(cur.add_size, 1)
                continue
            if cur.orig_filename != self.inf.orig_filename:
                raise BadRarFile("Did not found file entry")
            self.cur = cur
            self.cur_avail = cur.add_size
            return True

# string-to-key hashing
def rar3_s2k(psw, salt):
    seed = psw.encode('utf_16_le') + salt
    iv = EMPTY
    h = sha1()
    for i in range(16):
        for j in range(0x4000):
            cnt = S_LONG.pack(i*0x4000 + j)
            h.update(seed + cnt[:3])
            if j == 0:
                iv += h.digest()[-1]
    key_be = h.digest()[:16]
    key_le = pack("<LLLL", *unpack(">LLLL", key_be))
    return key_le, iv

# file-like object that decrypts from another file
class HeaderDecrypt:
    def __init__(self, f, key, iv):
        self.f = f
        self.ciph = AES.new(key, AES.MODE_CBC, iv)
        self.buf = EMPTY

    def tell(self):
        return self.f.tell()

    def read(self, cnt=None):
        if cnt > 8*1024:
            raise BadRarFile('Bad count to header decrypt - wrong password?')

        # consume old data
        if cnt <= len(self.buf):
            res = self.buf[:cnt]
            self.buf = self.buf[cnt:]
            return res
        res = self.buf
        self.buf = EMPTY
        cnt -= len(res)

        # decrypt new data
        BLK = self.ciph.block_size
        while cnt > 0:
            enc = self.f.read(BLK)
            if len(enc) < BLK:
                break
            dec = self.ciph.decrypt(enc)
            if cnt >= len(dec):
                res += dec
                cnt -= len(dec)
            else:
                res += dec[:cnt]
                self.buf = dec[cnt:]
                cnt = 0

        return res

