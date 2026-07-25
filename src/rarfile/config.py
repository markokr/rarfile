"""Runtime configurable variables.
"""

import sys

#: executable for unrar tool
UNRAR_TOOL = "unrar"

#: executable for unar tool
UNAR_TOOL = "unar"

#: executable for bsdtar tool
BSDTAR_TOOL = "bsdtar"

#: executable for tar tool
TAR_TOOL = "bsdtar"

#: executable for p7zip/7z tool
SEVENZIP_TOOL = "7z"

#: executable for alternative 7z tool
SEVENZIP2_TOOL = "7zz"

#: default fallback charset
DEFAULT_CHARSET = "windows-1252"

#: list of encodings to try, with fallback to DEFAULT_CHARSET if none succeed
TRY_ENCODINGS = ("utf8", "utf-16le")

#: whether to speed up decompression by using tmp archive
USE_EXTRACT_HACK = 1

#: limit the filesize for tmp archive usage
HACK_SIZE_LIMIT = 20 * 1024 * 1024

#: set specific directory for mkstemp() used by hack dir usage
HACK_TMP_DIR = None

#: Use external tool for non-compressed(stored) files
FORCE_TOOL = False

#: Separator for path name components.  Always "/".
PATH_SEP = "/"

#: Running on Windows?
WIN32 = sys.platform == "win32"

#: Default block size for copy operations
BSIZE = 512 * 1024 if WIN32 else 64 * 1024

#: Max size to scan for RAR signature
SFX_MAX_SIZE = 2 * 1024 * 1024

__all__ = (
    "BSDTAR_TOOL",
    "BSIZE",
    "DEFAULT_CHARSET",
    "FORCE_TOOL",
    "HACK_SIZE_LIMIT",
    "HACK_TMP_DIR",
    "PATH_SEP",
    "SEVENZIP2_TOOL",
    "SEVENZIP_TOOL",
    "SFX_MAX_SIZE",
    "TAR_TOOL",
    "TRY_ENCODINGS",
    "UNAR_TOOL",
    "UNRAR_TOOL",
    "USE_EXTRACT_HACK",
    "WIN32",
)
