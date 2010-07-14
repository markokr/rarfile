#! /usr/bin/env python

"""Dump archive contents, test extraction."""

import sys
import rarfile as rf
from binascii import crc32

usage = """
dumprar [switches] [ARC1 ARC2 ...] [@ARCLIST]
switches:
  @file      read archive names from file
  -pPSW      set password
  -Ccharset  set fallback charset
  -v         increase verbosity
  -t         attemt to read all files
  -x         write read files out
  -c         show archive comment
  -h         show usage
  --         stop switch parsing
""".strip()

os_list = ['DOS', 'OS2', 'WIN', 'UNIX', 'MACOS', 'BEOS']

block_strs = ['MARK', 'MAIN', 'FILE', 'OLD_COMMENT', 'OLD_EXTRA',
              'OLD_SUB', 'OLD_RECOVERY', 'OLD_AUTH', 'SUB', 'ENDARC']

def rarType(type):
    if type < rf.RAR_BLOCK_MARK or type > rf.RAR_BLOCK_ENDARC:
        return "*UNKNOWN*"
    return block_strs[type - rf.RAR_BLOCK_MARK]
                                 
main_bits = (
    (rf.RAR_MAIN_VOLUME, "VOL"),
    (rf.RAR_MAIN_COMMENT, "COMMENT"),
    (rf.RAR_MAIN_LOCK, "LOCK"),
    (rf.RAR_MAIN_SOLID, "SOLID"),
    (rf.RAR_MAIN_NEWNUMBERING, "NEWNR"),
    (rf.RAR_MAIN_AUTH, "AUTH"),
    (rf.RAR_MAIN_RECOVERY, "RECOVERY"),
    (rf.RAR_MAIN_PASSWORD, "PASSWORD"),
    (rf.RAR_MAIN_FIRSTVOLUME, "FIRSTVOL"),
    (rf.RAR_SKIP_IF_UNKNOWN, "SKIP"),
    (rf.RAR_LONG_BLOCK, "LONG"),
)

endarc_bits = (
    (rf.RAR_ENDARC_NEXT_VOLUME, "NEXTVOL"),
    (rf.RAR_ENDARC_DATACRC, "DATACRC"),
    (rf.RAR_ENDARC_REVSPACE, "REVSPACE"),
    (rf.RAR_SKIP_IF_UNKNOWN, "SKIP"),
    (rf.RAR_LONG_BLOCK, "LONG"),
)

file_bits = (
    (rf.RAR_FILE_SPLIT_BEFORE, "SPLIT_BEFORE"),
    (rf.RAR_FILE_SPLIT_AFTER, "SPLIT_AFTER"),
    (rf.RAR_FILE_PASSWORD, "PASSWORD"),
    (rf.RAR_FILE_COMMENT, "COMMENT"),
    (rf.RAR_FILE_SOLID, "SOLID"),
    (rf.RAR_FILE_LARGE, "LARGE"),
    (rf.RAR_FILE_UNICODE, "UNICODE"),
    (rf.RAR_FILE_SALT, "SALT"),
    (rf.RAR_FILE_VERSION, "VERSION"),
    (rf.RAR_FILE_EXTTIME, "EXTTIME"),
    (rf.RAR_FILE_EXTFLAGS, "EXTFLAGS"),
    (rf.RAR_SKIP_IF_UNKNOWN, "SKIP"),
    (rf.RAR_LONG_BLOCK, "LONG"),
)

generic_bits = (
    (rf.RAR_SKIP_IF_UNKNOWN, "SKIP"),
    (rf.RAR_LONG_BLOCK, "LONG"),
)

file_parms = ("D64", "D128", "D256", "D512",
              "D1024", "D2048", "D4096", "DIR")

def render_flags(flags, bit_list):
    res = []
    for bit in bit_list:
        if flags & bit[0]:
            res.append(bit[1])
    return ",".join(res)

def get_file_flags(flags):
    res = render_flags(flags, file_bits)

    xf = (flags & rf.RAR_FILE_DICTMASK) >> 5
    res += "," + file_parms[xf]
    return res

def get_main_flags(flags):
    return render_flags(flags, main_bits)

def get_endarc_flags(flags):
    return render_flags(flags, endarc_bits)

def get_generic_flags(flags):
    return render_flags(flags, generic_bits)

def fmt_time(t):
    return "%04d-%02d-%02d %02d:%02d:%02d" % t

def show_item(h):
    st = rarType(h.type)
    print("%s: hdrlen=%d datlen=%d hdr_unknown=%d" % (st, h.header_size,
                h.add_size, h.header_unknown))
    if h.header_unknown > 0:
        dat = h.header_data[-h.header_unknown:]
        print("  unknown:", repr(dat))
    if h.type in (rf.RAR_BLOCK_FILE, rf.RAR_BLOCK_SUB):
        if h.host_os == rf.RAR_OS_UNIX:
            s_mode = "0%o" % h.mode
        else:
            s_mode = "0x%x" % h.mode
        print("  flags=0x%04x:%s" % (h.flags, get_file_flags(h.flags)))
        if h.host_os >= 0 and h.host_os < len(os_list):
            s_os = os_list[h.host_os]
        else:
            s_os = "?"
        print("  os=%d:%s ver=%d mode=%s meth=%c cmp=%d dec=%d vol=%d" % (
                h.host_os, s_os,
                h.extract_version, s_mode, h.compress_type,
                h.compress_size, h.file_size, h.volume))
        ucrc = (h.CRC + (1 << 32)) & ((1 << 32) - 1)
        print("  crc=0x%08x (%d) time=%s" % (ucrc, h.CRC, fmt_time(h.date_time)))
        print("  name=%s" % h.filename)
        print("  name=%s" % h.unicode_filename)
        if h.mtime:
            print("  mtime=%s" % repr(h.mtime))
        if h.ctime:
            print("  ctime=%s" % repr(h.ctime))
        if h.atime:
            print("  atime=%s" % repr(h.atime))
        if h.arctime:
            print("  arctime=%s" % repr(h.arctime))
    elif h.type == rf.RAR_BLOCK_MAIN:
        print("  flags=0x%04x:%s" % (h.flags, get_main_flags(h.flags)))
    elif h.type == rf.RAR_BLOCK_ENDARC:
        print("  flags=0x%04x:%s" % (h.flags, get_endarc_flags(h.flags)))
    else:
        print("  flags=0x%04x:%s" % (h.flags, get_generic_flags(h.flags)))

cf_show_comment = 0
cf_verbose = 0
cf_charset = None
cf_extract = 0
cf_test_read = 0
cf_test_unrar = 0

def test_read_long(r, inf):
    f = r.open(inf.filename)
    total = 0
    crc = 0
    while 1:
        data = f.read(8192)
        if not data:
            break
        total += len(data)
        crc = crc32(data, crc)
    f.close()
    if total != inf.file_size:
        print("\n *** %s has corrupt file: %s ***" % (r.rarfile, inf.filename))
        print(" *** short read: got=%d, need=%d ***\n" % (total, inf.file_size))

def test_read(r, inf):
    if inf.file_size > 2*1024*1024:
        test_read_long(r, inf)
    else:
        dat = r.read(inf.filename)

def test_real(fn, psw):
    print("Archive: %s" % fn)

    cb = None
    if cf_verbose > 1:
        cb = show_item

    # check if rar
    if not rf.is_rarfile(fn):
        print(" --- %s is not a RAR file ---" % fn)
        return

    # open
    r = rf.RarFile(fn, charset = cf_charset, info_callback = cb)
    # set password
    if r.needs_password():
        if psw:
            r.setpassword(psw)
        else:
            print(" --- %s requires password ---" % fn)
            return

    # show comment
    if cf_show_comment and r.comment:
        for ln in r.comment.split('\n'):
            print("    %s" % ln)

    # process
    for n in r.namelist():
        inf = r.getinfo(n)
        if inf.isdir():
            continue
        if cf_verbose == 1:
            show_item(inf)
        if cf_test_read:
            test_read(r, inf)

    if cf_extract:
        r.extractall()
        for inf in r.infolist():
            r.extract(inf)

    if cf_test_unrar:
        r.testrar()

def test(fn, psw):
    try:
        test_real(fn, psw)
    except rf.BadRarFile:
        exc, msg, tb = sys.exc_info()
        print("\n *** %s ***\n" % (msg,))
        del tb
    except rf.NeedFirstVolume:
        print(" --- %s is middle part of multi-vol archive ---" % fn)
    except IOError:
        exc, msg, tb = sys.exc_info()
        print("\n *** %s ***\n" % (msg,))
        del tb

def main():
    global cf_verbose, cf_show_comment, cf_charset
    global cf_extract, cf_test_read, cf_test_unrar

    # parse args
    args = []
    psw = None
    noswitch = False
    for a in sys.argv[1:]:
        if noswitch:
            args.append(a)
        elif a[0] == "@":
            for ln in open(a[1:], 'r'):
                fn = ln[:-1]
                args.append(fn)
        elif a[0] != '-':
            args.append(a)
        elif a[1] == 'p':
            psw = a[2:]
        elif a == '--':
            noswitch = True
        elif a == '-h':
            print(usage)
            return
        elif a == '-v':
            cf_verbose += 1
        elif a == '-c':
            cf_show_comment = 1
        elif a == '-x':
            cf_extract = 1
        elif a == '-t':
            cf_test_read = 1
        elif a == '-T':
            cf_test_unrar = 1
        elif a[1] == 'C':
            cf_charset = a[2:]
        else:
            raise Exception("unknown switch: "+a)
    if not args:
        print(usage)

    for fn in args:
        test(fn, psw)

    
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass

