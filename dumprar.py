#! /usr/bin/env python

import sys, os
from StringIO import StringIO
from array import array
import rarfile as rf

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
        #val = 1 << bit[0]
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
    print "%s: hdrlen=%d datlen=%d hdr_unknown=%d" % (st, h.header_size,
                h.add_size, h.header_unknown)
    if h.header_unknown > 0:
        dat = h.header_data[-h.header_unknown:]
        print "  unknown:", repr(dat)
    if h.type in (rf.RAR_BLOCK_FILE, rf.RAR_BLOCK_SUB):
        if h.host_os == rf.RAR_OS_UNIX:
            s_mode = "0%o" % h.mode
        else:
            s_mode = "0x%x" % h.mode
        print "  flags=0x%04x:%s" % (h.flags, get_file_flags(h.flags))
        if h.host_os >= 0 and h.host_os < len(os_list):
            s_os = os_list[h.host_os]
        else:
            s_os = "?"
        print "  os=%d:%s ver=%d mode=%s meth=%c cmp=%d dec=%d" % (
                h.host_os, s_os,
                h.extract_version, s_mode, h.compress_type,
                h.compress_size, h.file_size)
        ucrc = (h.CRC + (1 << 32)) & (0xFFFFFFFF)
        print "  crc=0x%08x (%d) time=%s" % (ucrc, h.CRC, fmt_time(h.date_time))
        print "  name=%s" % h.unicode_filename
    elif h.type == rf.RAR_BLOCK_MAIN:
        print "  flags=0x%04x:%s" % (h.flags, get_main_flags(h.flags))
    elif h.type == rf.RAR_BLOCK_ENDARC:
        print "  flags=0x%04x:%s" % (h.flags, get_endarc_flags(h.flags))
    else:
        print "  flags=0x%04x:%s" % (h.flags, get_generic_flags(h.flags))

try:
    for fn in sys.argv[1:]:
        print "Rar:", fn
        rf.RarFile(fn, info_callback = show_item, charset="iso-8859-1")
except IOError:
    pass

