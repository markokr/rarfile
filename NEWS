
rarfile history
===============

Version 2.5 (2012-01-19)
------------------------

Fixes:

* .read() and .readinto() now do looping read to work properly
  on short reads.  Important for Python 3.2+ where read from pipe
  can return short result even on blocking file descriptor.
* Proper error reporting in .extract(), .extractall(), .testrar()
* .read() from unrar pipe: prefer to return unrar error code,
  if thats not available, do own error checks.
* Avoid string addition in .read(), instead use always list+join to
  merge multi-part reads.
* dumprar: dont re-encode byte strings (python 2.x).  This avoids
  unneccessary failure when printing invalid unicode.

Version 2.4 (2011-11-05)
------------------------

Fixes:

* USE_DATETIME: survive bad values from RAR
* Fix bug in corrupt unicode filename handling
* dumprar: make unicode chars work with both pipe and console

Version 2.3 (2011-07-03)
------------------------

Features:

* Support .seek() method on file streams.  (Kristian Larsson)
* Support .readinto() method on file streams.  Optimized implementation
  is available on Python 2.6+ where ``memoryview`` is available.
* Support file comments - ``RarInfo.comment`` contains decompressed data if available.
* File objects returned by ``RarFile.open()`` are ``io.RawIOBase``-compatible.
  They can further wrapped with ``io.BufferedReader` and ``io.TextIOWrapper``.
* Now .getinfo() uses dict lookup instead of sequential scan when
  searching archive entry.  This speeds up prococessing for archives that
  have many entries.
* Option ``rarfile.UNICODE_COMMENTS`` to decode both archive and file comments to unicode.
  It uses ``TRY_ENCODINGS`` for list of encodings to try.  If off, comments are
  left as byte strings.  Default: 0
* Option ``rarfile.PATH_SEP`` to change path separator.  Default: ``r'\'``,
  set ``rarfile.PATH_SEP='/'`` to be compatibe with zipfile.
* Option ``rarfile.USE_DATETIME`` to convert timestamps to datetime objects.
  Default: 0, timestamps are tuples.
* Option ``rarfile.TRY_ENCODINGS`` to allow tuning attempted encoding list.
* Reorder RarInfo fiels to better show zipfile-compatible fields.
* Standard regtests to make sure various features work

Compatibility:

* Drop ``RarInfo.unicode_filename``, plain ``RarInfo.filename`` is already unicode since 2.0.
* .read(-1) reads now until EOF.  Previously it returned empty buffer.

Fixes:

* Make encrypted headers work with Python 3.x bytes() and with old 2.x 'sha' module.
* Simplify ``subprocess.Popen()`` usage when launching ``unrar``.  Previously
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
* Use ``struct.Struct()`` to cache unpack formats.
* Support missing ``os.devnull``. (Python 2.3)

Version 2.1 (2010-07-31)
------------------------

Features:

* Minimal implmentation for .extract(), .extractall(), .testrar().
  They are simple shortcuts to ``unrar`` invocation.
* Accept RarInfo object where filename is expected.
* Include dumprar.py in .tgz.  It can be used to visualize RAR structure
  and test module.
* Support for encrypted file headers.

Fixes:

* Don't read past ENDARC, there could be non-RAR data there.
* RAR 2.x: It does not write ENDARC, but our volume code expected it.  Fix that.
* RAR 2.x: Support more than 200 old-style volumes.

Cleanups:

* Load comment only when requested.
* Cleanup of internal config variables.  They should have now final names.
* .open(): Add mode=r argument to match zipfile.
* Doc and comments cleanup, minimize duplication.
* Common wrappers for both compressed and uncompressed files,
  now .open() also does CRC-checking.

Version 2.0 (2010-04-29)
------------------------

Features:

* Python 3 support.  Still works with 2.x.
* Parses extended time fields. (.mtime, .ctime, .atime)
* .open() method.  This makes possible to process large
  entries that do not fit into memory.
* Supports password-protected archives.
* Supports archive comments.

Cleanups:

* Uses subprocess module to launch unrar.
* .filename is always Unicode string, .unicode_filename is now deprecated.
* .CRC is unsigned again, as python3 crc32() is unsigned.

Version 1.1 (2008-08-31)
------------------------

Fixes:

* Replace os.tempnam() with tempfile.mkstemp().  (Jason Moiron)
* Fix infinite loop in _extract_hack on unexpected EOF
* RarInfo.CRC is now signed value to match crc32()
* RarFile.read() now checks file crc

Cleanups:

* more docstrings
* throw proper exceptions (subclasses of rarfile.Error)
* RarInfo has fields pre-initialized, so they appear in help()
* rename RarInfo.data to RarInfo.header_data
* dont use "print" when header parsing fails
* use try/finally to delete temp rar

Version 1.0 (2005-08-08)
------------------------

* First release.

