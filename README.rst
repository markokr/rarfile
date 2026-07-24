rarfile
=======

This is Python module for RAR_ archive reading.
The interface follows the style of zipfile_.
Licensed under ISC_ license.

Features:

* Supports both RAR3 and RAR5 format archives.
* Supports multi volume archives.
* Supports Unicode filenames.
* Supports password-protected archives.
* Supports archive and file comments.
* Archive parsing and non-compressed files are handled in pure Python code.
* Compressed files are extracted by executing external tool:
  unrar_ (preferred), unar_, 7zip_ or bsdtar_.
* Works with Python 3.10+.

.. _RAR: https://en.wikipedia.org/wiki/RAR_%28file_format%29
.. _zipfile: https://docs.python.org/3/library/zipfile.html
.. _ISC: https://en.wikipedia.org/wiki/ISC_license
.. _bsdtar: https://github.com/libarchive/libarchive
.. _unrar: https://www.rarlab.com/
.. _unar: https://theunarchiver.com/command-line
.. _7zip: https://www.7-zip.org/

Backends:

+-------------+----------------------+-----------------------------------------------------+
| Backend     | Status               | Notes                                               |
+=============+======================+=====================================================+
| unrar_      | Supported            | * Recommended: full format support.                 |
+-------------+----------------------+-----------------------------------------------------+
| 7zip_       | Supported            | * Requires ``7zip-rar`` package on Debian/Ubuntu.   |
+-------------+----------------------+-----------------------------------------------------+
| p7zip_      | Supported            | * Requires ``p7zip-rar`` package on Debian/Ubuntu.  |
+-------------+----------------------+-----------------------------------------------------+
| unar_       | Supported            | * Does not support RAR2 locked files.               |
|             |                      | * Does not support RAR5 Blake2 hash checking.       |
+-------------+----------------------+-----------------------------------------------------+
| bsdtar_     | Supported            | * Does not support multi-volume archives.           |
|             |                      | * Does not support solid archives.                  |
|             |                      | * Does not support password-protected archives.     |
|             |                      | * Does not support RARVM-based compression filters. |
+-------------+----------------------+-----------------------------------------------------+
| unrar-free_ | Supported            | * Since v0.3.0 based on libarchive, same as bsdtar. |
|             |                      | * Supports multi-volume archives.                   |
+-------------+----------------------+-----------------------------------------------------+

.. _p7zip: https://github.com/p7zip-project/p7zip
.. _unrar-free: https://gitlab.com/bgermann/unrar-free

OS notes:

- Windows: default `tar` is `bsdtar`.
- MacOS: default `tar` is `bsdtar`.  Use MacPorts to install `rar`/`unrar`/`7zip`/`p7zip`,
  Homebrew is dropping RAR support.

Links:

- `Documentation`_
- `Downloads`_
- `Git`_ repo

.. _Git: https://github.com/markokr/rarfile
.. _Downloads: https://pypi.org/project/rarfile/#files
.. _Documentation: https://rarfile.readthedocs.io/
