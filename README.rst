
rarfile - RAR archive reader for Python
=======================================

This is Python module for RAR_ archive reading.  The interface
is made as zipfile_ like as possible.  Licensed under ISC_
license.

Features:

- Supports both RAR3 and RAR5 format archives.
- Supports multi volume archives.
- Supports Unicode filenames.
- Supports password-protected archives.
- Supports archive and file comments.
- Archive parsing and non-compressed files are handled in pure Python code.
- Compressed files are extracted by executing external tool: either ``unrar``
  from RARLAB_ or ``unar`` from TheUnarchiver_.
- Works with Python 3.6+.

Links:

- `Documentation`_
- `Downloads`_
- `Git`_ repo

.. _Git: https://github.com/markokr/rarfile
.. _Downloads: https://pypi.org/project/rarfile/
.. _Documentation: https://rarfile.readthedocs.io/
.. _RAR: https://en.wikipedia.org/wiki/RAR_%28file_format%29
.. _zipfile: https://docs.python.org/3/library/zipfile.html
.. _ISC: https://en.wikipedia.org/wiki/ISC_license
.. _libarchive: https://github.com/libarchive/libarchive
.. _RARLAB: https://www.rarlab.com/
.. _TheUnarchiver: https://theunarchiver.com/command-line
