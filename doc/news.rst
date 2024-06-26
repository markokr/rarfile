
rarfile history
===============

.. py:currentmodule:: rarfile

Version 4.2 (2024-04-03)
------------------------

Features:

* Support ``unrar-free`` >= 0.2.0.
  [`#103 <https://github.com/markokr/rarfile/pull/103>`_]
* Add :meth:`RarFile.is_solid` to check if archive uses
  solid compression.
  [`#101 <https://github.com/markokr/rarfile/issues/101>`_]

Fixes:

* Support old multi-volume archives better where ENDARC
  does not contain NEXTVOL.
  [`#97 <https://github.com/markokr/rarfile/issues/97>`_]

Cleanups:

* ci: Drop Python 3.7, add 3.12
* ci: upgrade actions

Version 4.1 (2023-09-17)
------------------------

Features:

* Support 7zip/p7zip as decompression backend.
  [`#71 <https://github.com/markokr/rarfile/issues/71>`_]
* RAR5: check password before trying to read file (chigusa)
  [`#79 <https://github.com/markokr/rarfile/pull/79>`_]

New APIs:

* Make get_rar_version a public function (Safihre)
  [`#63 <https://github.com/markokr/rarfile/pull/63>`_]
* New option: ``part_only`` for :class:`RarFile`,
  to read only single file and allow it to be middle-part
  of multi-volume archive.
* Add :meth:`RarFile.printdir`, use it in dumprar.  Needed to examine
  FILE_COPY or HARD_LINK entries that do not contain data.

Fixes:

* Use OS separator to access filename.  Should fix
  subdirectory entry access on Windows.
  [`#96 <https://github.com/markokr/rarfile/pull/96>`_]
* DirectReader: check seek position on each read.
  Fixes read reading from multiple entries in parallel
  on RarFile backed by file object.
  [`#81 <https://github.com/markokr/rarfile/pull/81>`_]
* DirectReader: properly disable CRC check when seeking.
  [`#73 <https://github.com/markokr/rarfile/issues/73>`_]
* Reset _hdrenc_main before processing a new volume.
  Fixes CRC checks on multi-volume reads.
  [`#80 <https://github.com/markokr/rarfile/pull/80>`_]
* Adapt to Python 3.10 argparse (MeggyCal)
  [`#85 <https://github.com/markokr/rarfile/pull/85>`_]
* SFX: Handle volume numbering special cases better.
* nsdatetime: support pypy internal use
* Throw error if backend does not support passwords.

Cleanups:

* ci: Use proper unrar on Windows.  MingW one tolaretes
  paths with ``/`` better than upstream build.
* ci: Add Python 3.10 to the testing (Christian Clauss)
  [`#76 <https://github.com/markokr/rarfile/pull/76>`_]
* Avoid isascii, not in 3.6

Version 4.0 (2020-07-31)
------------------------

Main goals are:

* Increased ``zipfile``-compatibility, thus also achieving smaller
  difference between RAR3 and RAR5 archives.
* Implement :meth:`RarFile.extract` on top of :meth:`RarFile.open` instead
  using ``unrar x`` directly, thus making maintenance of alternative backends
  more manageable.  Negative aspect of that is that there are features that
  internal extract code does not support - hard links, NTFS streams and
  junctions.

Breaking changes:

* Directory names will have "/" appended.
  [`#31 <https://github.com/markokr/rarfile/issues/31>`_]
* :meth:`RarFile.extract` operates only on single entry,
  so when used on directory it will create directory
  but not extract files under it.
* :meth:`RarFile.extract`/:meth:`RarFile.extractall`/:meth:`RarFile.testrar`
  will not launch special unrar command line, instead they are
  implemented on top of :meth:`RarFile.open`.
* Keyword args in top-level APIs were renamed to match zipfile:

  * RarFile(rarfile) -> RarFile(file)
  * RarFile.setpassword(password) -> .setpassword(pwd)
  * RarFile.getinfo(fname) -> .getinfo(name)
  * RarFile.open(fname, mode, psw) -> .open(name, mode, pwd)
  * RarFile.read(fname, psw) -> .read(name, pwd)

* :data:`PATH_SEP` cannot be changed from "/".

New features:

* :meth:`RarFile.extract` will return final sanitized filename for
  target file.
  [`#42 <https://github.com/markokr/rarfile/issues/42>`_,
  `#52 <https://github.com/markokr/rarfile/issues/52>`_]
* :meth:`RarInfo.is_dir` is now preferred spelling of ``isdir()``.
  Old method kept as alias.
  [`#44 <https://github.com/markokr/rarfile/issues/44>`_]
* New :meth:`RarInfo.is_file` and :meth:`RarInfo.is_symlink`
  methods. Only one of :meth:`~RarInfo.is_file`, :meth:`~RarInfo.is_dir`
  or :meth:`~RarInfo.is_symlink` can be True.
* :meth:`RarFile.printdir` has ``file`` argument for output.
* :meth:`RarFile.__iter__` loops over :class:`RarInfo` entries.
* RAR3: throw :exc:`NeedFirstVolume` exception with current volume number,
  like RAR5 does.
  [`#58 <https://github.com/markokr/rarfile/issues/58>`_]
* Nanosecond timestamp support.  Visible as :class:`nsdatetime`
  instance.
* Minimal CLI when run as script: ``python3 -m rarfile``
* Skip old file versions in versioned archive.

Cleanups:

* Use PBKDF2 implementation from :mod:`hashlib`.
* Improve test coverage.

Version 3.3 (2020-07-26)
------------------------

Fixes:

* Add the .sfx test files to MANIFEST.in for inclusion in pypi tarball.
  [`#60 <https://github.com/markokr/rarfile/issues/60>`_]
* Add all files in git to tarball.

Version 3.2 (2020-07-19)
------------------------

Breaking change:

* Top-level function ``custom_check()`` is removed as part
  of tool discovery refactor.

New features:

* Support ``unar`` as decompression backend.  It has much better
  support for RAR features than ``bsdtar``.
  [`#36 <https://github.com/markokr/rarfile/issues/36>`_]

* Support SFX archives - archive header is searched in first
  2MB of the file.
  [`#48 <https://github.com/markokr/rarfile/issues/48>`_]

* Add :data:`HACK_TMP_DIR` option, to force temp files into
  specific directory.
  [`#43 <https://github.com/markokr/rarfile/issues/43>`_]

Fixes:

* Always use "/" for path separator in command-line, gives better
  results on Windows.

Cleanups:

* Drop module-level options from docs, they create confusion.
  [`#47 <https://github.com/markokr/rarfile/issues/47>`_]

* Drop support for Python 2 and 3.5 and earlier.  Python 2 is dead
  and requiring Python 3.6 gives blake2s, stdlib that supports pathlib,
  and ordered dict without compat hacks.

* Replace PyCrypto with PyCryptodome in tests.

* Use Github Actions for CI.

Version 3.1 (2019-09-15)
------------------------

**This will be last version with support for Python 2.x**

New feature:

* Accept pathlib objects as filenames.
  (Aleksey Popov)

* Accept `bytes` filenames in Python 3
  (Nate Bogdanowicz)

Fixes:

* Use bug-compatible SHA1 for longer passwords (> 28 chars)
  in RAR3 encrypted headers.
  (Marko Kreen)

* Return true/false from _check_unrar_tool
  (miigotu)

* Include all test files in archive
  (Benedikt Morbach)

* Include volume number in NeedFirstVolume exception if available (rar5).

Cleanups:

* Convert tests to pytest.

Version 3.0 (2016-12-27)
------------------------

New feature:

* Support RAR5 archive format.  It is actually completely different
  archive format from RAR3 one, only is uses same file extension
  and tools are old one.

  Except incompatibilies noted below, most of code should notice no change,
  existing :class:`RarInfo` fields will continue using RAR3-compatible
  values (eg. :attr:`RarInfo.host_os`).  RAR5-specific values will use
  new fields.

Incompatibilities between rarfile v2.x and 3.x:

* Default :data:`PATH_SEP` is now '/' instead '\\'.

* Removed :data:`NEED_COMMENTS` option, comments are always extracted.

* Removed :data:`UNICODE_COMMENTS` option, they are always decoded.

* Removed :data:`USE_DATETIME` option, :attr:`RarInfo.date_time` is always tuple,
  :attr:`RarInfo.mtime`, :attr:`RarInfo.atime`, :attr:`RarInfo.ctime` and
  :attr:`RarInfo.arctime` are always :class:`datetime.datetime` objects.

Fixes:

* Fixed bug when calling rarfp.open() on a RarInfo structure.

Cleanups:

* Code refactor to allow 2 different file format parsers.

* Code cleanups to pass modern linters.

* New testing and linting setup based on Tox_.

* Use setuptools instead distutils for install.

.. _Tox: https://tox.readthedocs.io/en/latest/

Version 2.8 (2016-06-07)
------------------------

* Fix: support solid archives from in-memory file object.
  Full archive will be written out to temp file.
  [`#21 <https://github.com/markokr/rarfile/issues/21>`_]

* Fix: ask unrar stop switches scanning,
  to handle archive names starting with "-".
  (Alexander Shadchin)
  [`#12 <https://github.com/markokr/rarfile/pull/12>`_]

* Fix: add missing _parse_error variable to RarFile object.
  (Gregory Mazzola)
  [`#20 <https://github.com/markokr/rarfile/pull/20>`_]

* Fix: return proper boolean from :meth:`RarInfo.needs_password`.
  [`#22 <https://github.com/markokr/rarfile/issues/22>`_]

* Fix: do not insert non-string rarfile into exception string.
  (Tim Muller)
  [`#23 <https://github.com/markokr/rarfile/pull/23>`_]

* Fix: make :meth:`RarFile.extract` and :meth:`RarFile.testrar`
  support in-memory archives.

* Use cryptography_ module as preferred crypto backend.
  PyCrypto_ will be used as fallback.

* Cleanup: remove compat code for Python 2.4/2.5/2.6.

.. _cryptography: https://pypi.org/project/cryptography/
.. _PyCrypto: https://pypi.org/project/pycrypto/

Version 2.7 (2014-11-23)
------------------------

* Allow use of bsdtar_ as decompression backend.  It sits
  on top of libarchive_, which has support for reading RAR archives.

  Limitations of ``libarchive`` RAR backend:

  - Does not support solid archives.
  - Does not support password-protected archives.
  - Does not support "parsing filters" used for audio/image/executable data,
    so few non-solid, non-encrypted archives also fail.

  Now :mod:`rarfile` checks if ``unrar`` and if not then tries ``bsdtar``.
  If that works, then keeps using it.  If not then configuration
  stays with ``unrar`` which will then appear in error messages.

.. _bsdtar: https://github.com/libarchive/libarchive/wiki/ManPageBsdtar1
.. _libarchive: https://www.libarchive.org/

* Both :class:`RarFile` and :func:`is_rarfile` now accept file-like
  object.  Eg. :class:`io.BytesIO`.  Only requirement is that the object
  must be seekable.  This mirrors similar funtionality in zipfile.

  Based on patch by Chase Zhang.

* Uniform error handling.  :class:`RarFile` accepts ``errors="strict"``
  argument.

  Allow user to tune whether parsing and missing file errors will raise
  exception.  If error is not raised, the error string can be queried
  with :meth:`RarFile.strerror` method.

Version 2.6 (2013-04-10)
------------------------

* Add context manager support for :class:`RarFile` class.
  Both :class:`RarFile` and :class:`RarExtFile` support
  :keyword:`with` statement now.
  (Wentao Han)
* :meth:`RarFile.volumelist` method, returns filenames of archive volumes.
* Re-throw clearer error in case ``unrar`` is not found in ``PATH``.
* Sync new unrar4.x error code from ``rar.txt``.
* Use Sphinx for documentation, push docs to rtfd.org_

.. _rtfd.org: https://rarfile.readthedocs.org/

Version 2.5 (2012-01-19)
------------------------

Fixes:

* :meth:`RarExtFile.read` and :meth:`RarExtFile.readinto` now do looping read
  to work properly on short reads.  Important for Python 3.2+ where read from pipe
  can return short result even on blocking file descriptor.
* Proper error reporting in :meth:`RarFile.extract`, :meth:`RarFile.extractall`
  and  :meth:`RarFile.testrar`.
* :meth:`RarExtFile.read` from unrar pipe: prefer to return unrar error code,
  if thats not available, do own error checks.
* Avoid string addition in :meth:`RarExtFile.read`, instead use always list+join to
  merge multi-part reads.
* dumprar: dont re-encode byte strings (Python 2.x).  This avoids
  unneccessary failure when printing invalid unicode.

Version 2.4 (2011-11-05)
------------------------

Fixes:

* :data:`USE_DATETIME`: survive bad values from RAR
* Fix bug in corrupt unicode filename handling
* dumprar: make unicode chars work with both pipe and console

Version 2.3 (2011-07-03)
------------------------

Features:

* Support .seek() method on file streams.  (Kristian Larsson)
* Support .readinto() method on file streams.  Optimized implementation
  is available on Python 2.6+ where :class:`memoryview` is available.
* Support file comments - :attr:`RarInfo.comment` contains decompressed data if available.
* File objects returned by :meth:`RarFile.open()` are :class:`io.RawIOBase`-compatible.
  They can further wrapped with :class:`io.BufferedReader` and :class:`io.TextIOWrapper`.
* Now .getinfo() uses dict lookup instead of sequential scan when
  searching archive entry.  This speeds up prococessing for archives that
  have many entries.
* Option :data:`UNICODE_COMMENTS` to decode both archive and file comments to unicode.
  It uses :data:`TRY_ENCODINGS` for list of encodings to try.  If off, comments are
  left as byte strings.  Default: 0
* Option :data:`PATH_SEP` to change path separator.  Default: ``r'\'``,
  set ``rarfile.PATH_SEP='/'`` to be compatibe with zipfile.
* Option :data:`USE_DATETIME` to convert timestamps to datetime objects.
  Default: 0, timestamps are tuples.
* Option :data:`TRY_ENCODINGS` to allow tuning attempted encoding list.
* Reorder :class:`RarInfo` fiels to better show zipfile-compatible fields.
* Standard regtests to make sure various features work

Compatibility:

* Drop :attr:`RarInfo.unicode_filename`, plain :attr:`RarInfo.filename` is already unicode since 2.0.
* .read(-1) reads now until EOF.  Previously it returned empty buffer.

Fixes:

* Make encrypted headers work with Python 3.x bytes() and with old 2.x 'sha' module.
* Simplify :class:`subprocess.Popen` usage when launching ``unrar``.  Previously
  it tried to optimize and work around OS/Python bugs, but this is not
  maintainable.
* Use temp rar file hack on multi-volume archives too.
* Always .wait() on unrar, to avoid zombies
* Convert struct.error to BadRarFile
* Plug some fd leaks.  Affected: Jython, PyPy.
* Broken archives are handled more robustly.

Version 2.2 (2010-08-19)
------------------------

Fixes:

* Relaxed volume naming.  Now it just calculates new volume name by finding number
  in old one and increasing it, without any expectations what that number should be.
* Files with 4G of compressed data in one colume were handled wrong.  Fix.
* DOS timestamp seconds need to be multiplied with 2.
* Correct EXTTIME parsing.

Cleanups:

* Compressed size is per-volume, sum them together, so that user sees complete
  compressed size for files split over several volumes.
* dumprar: Show unknown bits.
* Use :class:`struct.Struct` to cache unpack formats.
* Support missing :data:`os.devnull`. (Python 2.3)

Version 2.1 (2010-07-31)
------------------------

Features:

* Minimal implmentation for :meth:`RarFile.extract`, :meth:`RarFile.extractall`, :meth:`RarFile.testrar`.
  They are simple shortcuts to ``unrar`` invocation.
* Accept :class:`RarInfo` object where filename is expected.
* Include ``dumprar.py`` in .tgz.  It can be used to visualize RAR structure
  and test module.
* Support for encrypted file headers.

Fixes:

* Don't read past ENDARC, there could be non-RAR data there.
* RAR 2.x: It does not write ENDARC, but our volume code expected it.  Fix that.
* RAR 2.x: Support more than 200 old-style volumes.

Cleanups:

* Load comment only when requested.
* Cleanup of internal config variables.  They should have now final names.
* :meth:`RarFile.open`: Add mode=r argument to match zipfile.
* Doc and comments cleanup, minimize duplication.
* Common wrappers for both compressed and uncompressed files,
  now :meth:`RarFile.open` also does CRC-checking.

Version 2.0 (2010-04-29)
------------------------

Features:

* Python 3 support.  Still works with 2.x.
* Parses extended time fields. (.mtime, .ctime, .atime)
* :meth:`RarFile.open` method.  This makes possible to process large
  entries that do not fit into memory.
* Supports password-protected archives.
* Supports archive comments.

Cleanups:

* Uses :mod:`subprocess` module to launch ``unrar``.
* .filename is always Unicode string, .unicode_filename is now deprecated.
* .CRC is unsigned again, as python3 crc32() is unsigned.

Version 1.1 (2008-08-31)
------------------------

Fixes:

* Replace :func:`os.tempnam` with :func:`tempfile.mkstemp`.  (Jason Moiron)
* Fix infinite loop in _extract_hack on unexpected EOF
* :attr:`RarInfo.CRC` is now signed value to match crc32()
* :meth:`RarFile.read` now checks file crc

Cleanups:

* more docstrings
* throw proper exceptions (subclasses of :exc:`rarfile.Error`)
* RarInfo has fields pre-initialized, so they appear in help()
* rename RarInfo.data to RarInfo.header_data
* dont use "print" when header parsing fails
* use try/finally to delete temp rar

Version 1.0 (2005-08-08)
------------------------

* First release.

