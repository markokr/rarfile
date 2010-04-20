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
"""

import sys, os, re
from struct import pack, unpack
from binascii import crc32
from tempfile import mkstemp
from subprocess import Popen, PIPE

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

# py2.6 has broken bytes()
if sys.hexversion < 0x3000000:
    def bytes(foo, enc):
        return str(foo)

# export only interesting items
__all__ = ['is_rarfile', 'RarInfo', 'RarFile']

# whether to speed up decompression by using tmp archive
_use_extract_hack = 1

# command line to use for extracting (arch, file) will be added
_extract_cmd = ('unrar', 'p', '-inul')

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

#
# rar constants
#

RAR_ID = bytes("Rar!\x1a\x07\x00", 'ascii')
ZERO = bytes("\0", 'ascii')
EMPTY = bytes("", 'ascii')

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

# main header flags
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

# file header flags
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

RAR_ENDARC_NEXT_VOLUME  = 0x0001
RAR_ENDARC_DATACRC      = 0x0002
RAR_ENDARC_REVSPACE     = 0x0004

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

#
# Public interface
#

def is_rarfile(fn):
    '''Check quickly whether file is rar archive.'''
    buf = open(fn, "rb").read(len(RAR_ID))
    return buf == RAR_ID

class RarInfo:
    '''An entry in rar archive.'''

    __slots__ = (
        'compress_size',
        'file_size',
        'host_os',
        'CRC',
        'extract_version',
        'compress_type',
        'mode',
        'flags',
        'type',

        # unicode string
        'filename',

        # tuple of (year, mon, day, hr, min, sec)
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
        'orig_filename',
        'name_size',
        'header_size',
        'header_crc',
        'file_offset',
        'add_size',
        'header_data',
        'header_unknown',
        'header_offset',
        'volume',
        'salt',
        'ext_time',
    )

    def isdir(self):
        '''Returns True if the entry is a directory.'''
        if self.type == RAR_BLOCK_FILE:
            return (self.flags & RAR_FILE_DIRECTORY) == RAR_FILE_DIRECTORY
        return False

class RarFile:
    '''Rar archive handling.'''
    def __init__(self, rarfile, mode="r", charset=None, info_callback=None):
        self.rarfile = rarfile
        self.charset = charset

        self.info_list = []
        self.is_solid = 0
        self.uses_newnumbering = 0
        self.uses_volumes = 0
        self.info_callback = info_callback
        self.got_mainhdr = 0
        self._gen_volname = self._gen_oldvol

        if mode != "r":
            raise NotImplementedError("RarFile supports only mode=r")

        self._parse()

    def namelist(self):
        '''Return list of filenames in rar'''
        res = []
        for f in self.info_list:
            res.append(f.filename)
        return res

    def infolist(self):
        '''Return rar entries.'''
        return self.info_list

    def getinfo(self, fname):
        '''Return RarInfo for fname.'''
        fname2 = fname.replace("/", "\\")
        for f in self.info_list:
            if fname == f.filename or fname2 == f.filename:
                return f

    def read(self, fname):
        '''Return decompressed data.'''
        inf = self.getinfo(fname)
        if not inf:
            raise NoRarEntry("No such file")

        if inf.isdir():
            raise TypeError("Directory does not have any data")

        if inf.compress_type == 0x30:
            res = self._extract_clear(inf)
        elif _use_extract_hack and not self.is_solid and not self.uses_volumes:
            res = self._extract_hack(inf)
        else:
            res = self._extract_unrar(self.rarfile, inf)

        # python 2.x crc32() returns signed values
        crc = crc32(res)
        if crc < 0:
            crc += long(1) << 32

        if crc != inf.CRC:
            raise BadRarFile('CRC check failed: (%08x != %08x)' % (crc, inf.CRC))

        return res

    def close(self):
        """Release open resources."""
        pass

    def printdir(self):
        """Print archive file list to stdout."""
        for f in self.info_list:
            print(f.filename)

    # store entry
    def _process_entry(self, item):
        # RAR_BLOCK_NEWSUB has files too: CMT, RR
        if item.type == RAR_BLOCK_FILE:
            # use only first part
            if (item.flags & RAR_FILE_SPLIT_BEFORE) == 0:
                self.info_list.append(item)

        if self.info_callback:
            self.info_callback(item)

    # read rar
    def _parse(self):
        fd = open(self.rarfile, "rb")
        id = fd.read(len(RAR_ID))
        if id != RAR_ID:
            raise NotRarFile("Not a Rar archive")
        
        volume = 0  # first vol (.rar) is 0
        more_vols = 0
        while 1:
            h = self._parse_header(fd)
            if not h:
                if more_vols:
                    volume += 1
                    fd = open(self._gen_volname(volume), "rb")
                    more_vols = 0
                    if fd:
                        continue
                break
            h.volume = volume

            if h.type == RAR_BLOCK_MAIN and not self.got_mainhdr:
                if h.flags & RAR_MAIN_NEWNUMBERING:
                    self.uses_newnumbering = 1
                    self._gen_volname = self._gen_newvol
                self.uses_volumes = h.flags & RAR_MAIN_VOLUME
                self.is_solid = h.flags & RAR_MAIN_SOLID
                self.got_mainhdr = 1
            elif h.type == RAR_BLOCK_ENDARC:
                more_vols = h.flags & RAR_ENDARC_NEXT_VOLUME

            # store it
            self._process_entry(h)

            # go to next header
            if h.add_size > 0:
                fd.seek(h.file_offset + h.add_size, 0)

    # read single header
    def _parse_header(self, fd):
        h = self._parse_block_header(fd)
        if h and (h.type == RAR_BLOCK_FILE or h.type == RAR_BLOCK_SUB):
            self._parse_file_header(h)
        return h

    # common header
    def _parse_block_header(self, fd):
        HDRLEN = 7
        h = RarInfo()
        h.header_offset = fd.tell()
        buf = fd.read(HDRLEN)
        if not buf:
            return None

        t = unpack("<HBHH", buf)
        h.header_crc, h.type, h.flags, h.header_size = t
        h.header_unknown = h.header_size - HDRLEN

        if h.header_size > HDRLEN:
            h.header_data = fd.read(h.header_size - HDRLEN)
        else:
            h.header_data = EMPTY
        h.file_offset = fd.tell()

        if h.flags & RAR_LONG_BLOCK:
            h.add_size = unpack("<L", h.header_data[:4])[0]
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
        HDRLEN = 4+4+1+4+4+1+1+2+4
        fld = unpack("<LLBLLBBHL", h.header_data[ : HDRLEN])
        h.compress_size = fld[0]
        h.file_size = fld[1]
        h.host_os = fld[2]
        h.CRC = fld[3]
        h.date_time = self._parse_dos_time(fld[4])
        h.extract_version = fld[5]
        h.compress_type = fld[6]
        h.name_size = fld[7]
        h.mode = fld[8]
        pos = HDRLEN

        if h.flags & RAR_FILE_LARGE:
            h1, h2 = unpack("<LL", h.header_data[pos:pos+8])
            h.compress_size |= h1 << 32
            h.file_size |= h2 << 32
            pos += 8

        name = h.header_data[pos : pos + h.name_size ]
        pos += h.name_size
        if h.flags & RAR_FILE_UNICODE:
            nul = name.find(ZERO)
            h.orig_filename = name[:nul]
            u = _UnicodeFilename(h.orig_filename, name[nul + 1 : ])
            h.unicode_filename = u.decode()
        else:
            h.orig_filename = name
            if self.charset:
                h.unicode_filename = name.decode(self.charset)
            else:
                # just guessing...
                h.unicode_filename = name.decode("iso-8859-1", "replace")

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
        return (yr, mon, day, hr, min, sec)

    def _parse_ext_time(self, h, pos):
        data = h.header_data
        flags = unpack("<H", data[pos : pos + 2])[0]
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
                t = unpack("<I", data[pos : pos + 4])[0]
                dostime = self._parse_dos_time(t)
                pos += 4
            rem = 0
            cnt = flag & 3
            for i in range(3):
                rem <<= 8
                if i < cnt:
                    rem += unpack("B", data[pos : pos + 1])[0]
                    pos += 1
            sec = dostime[5] + rem / unit
            if flag & 4:
                sec += 1
            dostime = dostime[:5] + (sec,)
        return dostime, pos
        
    # new-style volume name
    def _gen_newvol(self, volume):
        # allow % in filenames
        fn = self.rarfile.replace("%", "%%")

        m = re.search(r"([0-9][0-9]*)[^0-9]*$", fn)
        if not m:
            raise BadRarName("Cannot construct volume name")
        n1 = m.start(1)
        n2 = m.end(1)
        fmt = "%%0%dd" % (n2 - n1)
        volfmt = fn[:n1] + fmt + fn[n2:]
        return volfmt % (volume + 1)

    # old-style volume naming
    def _gen_oldvol(self, volume):
        if volume == 0: return self.rarfile
        i = self.rarfile.rfind(".")
        base = self.rarfile[:i]
        if volume <= 100:
            ext = ".r%02d" % (volume - 1)
        else:
            ext = ".s%02d" % (volume - 101)
        return base + ext

    # read uncompressed file
    def _extract_clear(self, inf):
        volume = inf.volume
        buf = EMPTY
        cur = None
        while 1:
            f = open(self._gen_volname(volume), "rb")
            if not cur:
                f.seek(inf.header_offset)

            while 1:
                cur = self._parse_header(f)
                if cur.type in (RAR_BLOCK_MARK, RAR_BLOCK_MAIN):
                    if cur.add_size:
                        f.seek(cur.add_size, 1)
                    continue
                if cur.filename == inf.filename:
                    buf += f.read(cur.add_size)
                    break

                raise BadRarFile("Did not found file entry")

            # no more parts?
            if (cur.flags & RAR_FILE_SPLIT_AFTER) == 0:
                break

            volume += 1

        return buf

    # put file compressed data into temporary .rar archive, and run
    # unrar on that, thus avoiding unrar going over whole archive
    def _extract_hack(self, inf):
        BSIZE = 32*1024

        size = inf.compress_size + inf.header_size
        rf = open(self.rarfile, "rb")
        rf.seek(inf.header_offset)

        tmpfd, tmpname = mkstemp(suffix='.rar')
        tmpf = os.fdopen(tmpfd, "wb")
        
        try:
            # create main header: crc, type, flags, size, res1, res2
            mh = pack("<HBHHHL", 0x90CF, 0x73, 0, 13, 0, 0)
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

            buf = self._extract_unrar(tmpname, inf)
            return buf
        finally:
            os.unlink(tmpname)

    # extract using unrar
    def _extract_unrar(self, rarfile, inf):
        fn = inf.filename

        # unrar wants native separator
        fn = fn.replace("\\", os.sep)

        cmd = list(_extract_cmd)
        cmd.append(rarfile)
        cmd.append(fn)

        # 3xPIPE seems unreliable, at least on osx
        try:
            null = open("/dev/null", "wb")
            _in = null
            _err = null
        except IOError:
            _in = PIPE
            _err = PIPE

        # run unrar
        p = Popen(cmd, stdout = PIPE, stdin = _in, stderr = _err)
        data, errmsg = p.communicate()
        ret = p.returncode
        if ret != 0:
            raise BadRarFile("Error while unpacking file")
        return data

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

