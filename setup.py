#! /usr/bin/env python

from distutils.core import setup

longdesc = """
This is Python module for Rar archive reading.  The interface
is made as `zipfile` like as possible.

The archive structure parsing and uncompressed files
are handled in pure Python.  Decompression is done
via 'unrar' command line utility.

Features:

- Works with both Python 2.x and 3.x
- Supports RAR 3.x archives.
- Supports multi volume archives.
- Supports Unicode filenames.
- Supports password-protected archives.
- Supports archive comments.

Missing features:

- File comment handling.
- Decompression through unrarlib and/or unrar.dll.

"""

setup(
    name = "rarfile",
    version = "2.0",
    description = "Reader for RAR archives",
    author = "Marko Kreen",
    license = "ISC",
    author_email = "markokr@gmail.com",
    url = "http://rarfile.berlios.de/",
    long_description = longdesc.strip(),
    py_modules = ['rarfile'],
    keywords = ['rar', 'archive'],
    classifiers = [
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: ISC License (ISCL)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Archiving :: Compression",
    ]
)

