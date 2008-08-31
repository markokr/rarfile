#! /usr/bin/env python

import sys
from distutils.core import setup

longdesc = """\
This is Python module for Rar archive reading.  The interface
is made as `zipfile` like as possible.

The archive structure parsing and uncompressed files
are handled in pure python, for compressed files
is calls 'unrar' command line utility.

Features:

- Supports RAR 3.x archives.
- Supports multi volume archives.
- Supports Unicode filenames.

Missing features:

- Password-protected archives.
- Comment handling. (archive, file)
- Decompression through unrarlib and/or unrar.dll.

"""

setup(
    name = "rarfile",
    version = "1.1",
    description = "Reader for RAR archives",
    author = "Marko Kreen",
    license = "BSD",
    author_email = "markokr@gmail.com",
    url = "http://rarfile.berlios.de/",
    long_description = longdesc,
    py_modules = ['rarfile'],
    keywords = ['rar', 'archive'],
    classifiers = [
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ]
)

