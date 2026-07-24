__all__ = (
    "Error",
    "BadRarFile",
    "NotRarFile",
    "BadRarName",
    "NoRarEntry",
    "PasswordRequired",
    "BadSymLinkError",
    "NeedFirstVolume",
    "NoCrypto",
    "RarExecError",
    "RarWarning",
    "RarFatalError",
    "RarCRCError",
    "RarLockedArchiveError",
    "RarWriteError",
    "RarOpenError",
    "RarUserError",
    "RarMemoryError",
    "RarCreateError",
    "RarNoFilesError",
    "RarUserBreak",
    "RarWrongPassword",
    "RarUnknownError",
    "RarSignalExit",
    "RarCannotExec",
    "UnsupportedWarning",
)


class Error(Exception):
    """Base class for rarfile errors."""


class BadRarFile(Error):
    """Incorrect data in archive."""


class NotRarFile(Error):
    """The file is not RAR archive."""


class BadRarName(Error):
    """Cannot guess multipart name components."""


class NoRarEntry(Error):
    """File not found in RAR"""


class PasswordRequired(Error):
    """File requires password"""


class BadSymLinkError(Error):
    """Invalid symbolic link"""


class NeedFirstVolume(Error):
    """Need to start from first volume.

    Attributes:

        current_volume
            Volume number of current file or None if not known
    """

    def __init__(self, msg, volume):
        super().__init__(msg)
        self.current_volume = volume


class NoCrypto(Error):
    """Cannot parse encrypted headers - no crypto available."""


class RarExecError(Error):
    """Problem reported by unrar/rar."""


class RarWarning(RarExecError):
    """Non-fatal error"""


class RarFatalError(RarExecError):
    """Fatal error"""


class RarCRCError(RarExecError):
    """CRC error during unpacking"""


class RarLockedArchiveError(RarExecError):
    """Must not modify locked archive"""


class RarWriteError(RarExecError):
    """Write error"""


class RarOpenError(RarExecError):
    """Open error"""


class RarUserError(RarExecError):
    """User error"""


class RarMemoryError(RarExecError):
    """Memory error"""


class RarCreateError(RarExecError):
    """Create error"""


class RarNoFilesError(RarExecError):
    """No files that match pattern were found"""


class RarUserBreak(RarExecError):
    """User stop"""


class RarWrongPassword(RarExecError):
    """Incorrect password"""


class RarUnknownError(RarExecError):
    """Unknown exit code"""


class RarSignalExit(RarExecError):
    """Unrar exited with signal"""


class RarCannotExec(RarExecError):
    """Executable not found."""


class UnsupportedWarning(UserWarning):
    """Archive uses feature that are unsupported by rarfile.

    .. versionadded:: 4.0
    """
