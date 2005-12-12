#! /usr/bin/env python

import sys, os
from StringIO import StringIO
from array import array
from rarfile import *

os_list = ['DOS', 'OS2', 'WIN', 'UNIX']

block_strs = ['MARK', 'MAIN', 'FILE', 'OLD_COMMENT', 'OLD_EXTRA',
              'OLD_SUB', 'OLD_RECOVERY', 'OLD_AUTH', 'SUB', 'ENDARC']

def rarType(type):
    if type < RAR_BLOCK_MARK or type > RAR_BLOCK_ENDARC:
        return "*UNKNOWN*"
    return block_strs[type - RAR_BLOCK_MARK]
                                 
main_bits = (
    (RAR_MAIN_VOLUME, "VOL"),
    (RAR_MAIN_COMMENT, "COMMENT"),
    (RAR_MAIN_LOCK, "LOCK"),
    (RAR_MAIN_SOLID, "SOLID"),
    (RAR_MAIN_NEWNUMBERING, "NEWNR"),
    (RAR_MAIN_AUTH, "AUTH"),
    (RAR_MAIN_RECOVERY, "RECOVERY"),
    (RAR_MAIN_PASSWORD, "PASSWORD"),
    (RAR_MAIN_FIRSTVOLUME, "FIRSTVOL"),
    (RAR_SKIP_IF_UNKNOWN, "SKIP"),
    (RAR_LONG_BLOCK, "LONG"),
)

endarc_bits = (
    (RAR_ENDARC_NEXT_VOLUME, "NEXTVOL"),
    (RAR_ENDARC_DATACRC, "DATACRC"),
    (RAR_ENDARC_REVSPACE, "REVSPACE"),
    (RAR_SKIP_IF_UNKNOWN, "SKIP"),
    (RAR_LONG_BLOCK, "LONG"),
)

file_bits = (
    (RAR_FILE_SPLIT_BEFORE, "SPLIT_BEFORE"),
    (RAR_FILE_SPLIT_AFTER, "SPLIT_AFTER"),
    (RAR_FILE_PASSWORD, "PASSWORD"),
    (RAR_FILE_COMMENT, "COMMENT"),
    (RAR_FILE_SOLID, "SOLID"),
    (RAR_FILE_LARGE, "LARGE"),
    (RAR_FILE_UNICODE, "UNICODE"),
    (RAR_FILE_SALT, "SALT"),
    (RAR_FILE_VERSION, "VERSION"),
    (RAR_FILE_EXTTIME, "EXTTIME"),
    (RAR_FILE_EXTFLAGS, "EXTFLAGS"),
    (RAR_SKIP_IF_UNKNOWN, "SKIP"),
    (RAR_LONG_BLOCK, "LONG"),
)

generic_bits = (
    (RAR_SKIP_IF_UNKNOWN, "SKIP"),
    (RAR_LONG_BLOCK, "LONG"),
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

    xf = (flags & RAR_FILE_DICTMASK) >> 5
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
        dat = h.data[-h.header_unknown:]
        print "  unknown:", repr(dat)
    if h.type in (RAR_BLOCK_FILE, RAR_BLOCK_SUB):
        if h.host_os == RAR_OS_UNIX:
            s_mode = "0%o" % h.mode
        else:
            s_mode = "0x%x" % h.mode
        print "  flags=0x%04x:%s" % (h.flags, get_file_flags(h.flags))
        print "  os=%d:%s ver=%d mode=%s meth=%c cmp=%d dec=%d" % (
                h.host_os, os_list[h.host_os],
                h.extract_version, s_mode, h.compress_type,
                h.compress_size, h.file_size)
        print "  crc=0x%08x time=%s" % (h.CRC, fmt_time(h.date_time))
        print "  name=%s" % h.unicode_filename
    elif h.type == RAR_BLOCK_MAIN:
        print "  flags=0x%04x:%s" % (h.flags, get_main_flags(h.flags))
    elif h.type == RAR_BLOCK_ENDARC:
        print "  flags=0x%04x:%s" % (h.flags, get_endarc_flags(h.flags))
    else:
        print "  flags=0x%04x:%s" % (h.flags, get_generic_flags(h.flags))

for fn in sys.argv[1:]:
    print "Rar:", fn
    RarFile(fn, info_callback = show_item, charset="iso-8859-1")

