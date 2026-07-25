"""RAR archive reader.

This is Python module for Rar archive reading.  The interface
is made as :mod:`zipfile`-like as possible.

Basic logic:
 - Parse archive structure with Python.
 - Extract non-compressed files with Python
 - Extract compressed files with unrar.
 - Optionally write compressed data to temp file to speed up unrar,
   otherwise it needs to scan whole archive on each execution.

Example::

    import rarfile

    rf = rarfile.RarFile("myarchive.rar")
    for f in rf.infolist():
        print(f.filename, f.file_size)
        if f.filename == "README":
            print(rf.read(f))

Archive files can also be accessed via file-like object returned
by :meth:`RarFile.open`::

    import rarfile

    with rarfile.RarFile("archive.rar") as rf:
        with rf.open("README") as f:
            for ln in f:
                print(ln.strip())

For decompression to work, either ``unrar`` or ``unar`` tool must be in PATH.
"""


# ruff: noqa: F401, PLE0604

from .archive import *
from .archive import __all__ as _archive_all
from .backend import *
from .backend import __all__ as _backend_all
from .bits import *
from .bits import __all__ as _bits_all
from .cli import *
from .cli import __all__ as _cli_all
from .config import *
from .config import __all__ as _config_all
from .crypto import *
from .crypto import __all__ as _crypto_all
from .crypto import have_crypto as _have_crypto
from .errors import *
from .errors import __all__ as _errors_all
from .format import *
from .format import __all__ as _format_all
from .stream import *
from .stream import __all__ as _stream_all
from .utils import *
from .utils import __all__ as _utils_all

__all_available__ = (
    *_archive_all, *_bits_all, *_backend_all, *_config_all, *_cli_all,
    *_crypto_all, *_errors_all, *_format_all, *_stream_all, *_utils_all,
)

__all__ = ("get_rar_version", "is_rarfile", "is_rarfile_sfx", "RarInfo", "RarFile", "RarExtFile")

__version__ = "4.4"
