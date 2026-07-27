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
from .backend import *
from .bits import *
from .cli import *
from .config import *
from .crypto import *
from .crypto import have_crypto as _have_crypto
from .errors import *
from .format import *
from .info import *
from .stream import *
from .utils import *

__all__ = ("get_rar_version", "is_rarfile", "is_rarfile_sfx", "RarInfo", "RarFile", "RarExtFile")

__version__ = "5.0.dev1"
