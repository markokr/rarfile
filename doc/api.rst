
rarfile API documentation
=========================

.. contents:: Table Of Contents

Introduction
------------

.. automodule:: rarfile

RarFile class
-------------

.. autoclass:: RarFile
   :members:
   :special-members: __enter__, __exit__, __iter__

RarInfo class
-------------

.. autoclass:: RarInfo()
    :show-inheritance:
    :members:

RarEntry class
--------------

.. autoclass:: RarEntry()
    :members:

RarExtFile class
----------------

.. autoclass:: RarExtFile()
   :show-inheritance:
   :members:
   :inherited-members:
   :exclude-members: truncate, flush

nsdatetime class
----------------

.. autoclass:: nsdatetime(..., *, fold = 0, nanosecond = 0)
   :show-inheritance:
   :exclude-members: replace

   .. autoattribute:: nanosecond
   .. automethod:: astimezone
   .. automethod:: isoformat
   .. automethod:: replace(..., nanosecond = 0)

Functions
---------

.. autofunction:: is_rarfile
.. autofunction:: is_rarfile_sfx

Constants
---------

.. py:currentmodule:: rarfile.bits
.. automodule:: rarfile.bits
   :members:
.. py:currentmodule:: rarfile

Warnings
--------

.. autoclass:: UnsupportedWarning

Exceptions
----------

.. autoclass:: Error
.. autoclass:: BadRarFile
.. autoclass:: NotRarFile
.. autoclass:: BadRarName
.. autoclass:: NoRarEntry
.. autoclass:: PasswordRequired
.. autoclass:: BadSymLinkError
.. autoclass:: NeedFirstVolume
.. autoclass:: NoCrypto
.. autoclass:: RarExecError
.. autoclass:: RarWarning
.. autoclass:: RarFatalError
.. autoclass:: RarCRCError
.. autoclass:: RarLockedArchiveError
.. autoclass:: RarWriteError
.. autoclass:: RarOpenError
.. autoclass:: RarUserError
.. autoclass:: RarMemoryError
.. autoclass:: RarCreateError
.. autoclass:: RarNoFilesError
.. autoclass:: RarUserBreak
.. autoclass:: RarWrongPassword
.. autoclass:: RarUnknownError
.. autoclass:: RarSignalExit
.. autoclass:: RarCannotExec

Types
-----

.. autotype is broken in sphinx 9.1

.. py:type:: DateTuple
    :canonical: tuple[int, int, int, int, int, int]

    Type for date components.

.. py:type:: PathLike
    :canonical: str | bytes | ~pathlib.Path

    Type for file names.

.. autoclass:: FileLike()
    :show-inheritance:

    .. automethod:: read
    .. automethod:: seek
    .. automethod:: tell
    .. automethod:: close

.. autoclass:: RawFileLike()
    :show-inheritance:

    .. automethod:: read
    .. automethod:: readinto
    .. automethod:: seek
    .. automethod:: tell
    .. automethod:: close
