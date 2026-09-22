"""unseal：zip 与 tar 的解包工具，纯标准库。"""

from .entries import (
    KIND_DIR,
    KIND_FILE,
    KIND_HARDLINK,
    KIND_SYMLINK,
    ArchiveError,
    Entry,
    iter_archive,
)
from .extract import (
    DEFAULT_MAX_ENTRY_BYTES,
    EntryResult,
    ExtractError,
    ExtractReport,
    Extractor,
)

__all__ = [
    "ArchiveError",
    "DEFAULT_MAX_ENTRY_BYTES",
    "Entry",
    "EntryResult",
    "ExtractError",
    "ExtractReport",
    "Extractor",
    "KIND_DIR",
    "KIND_FILE",
    "KIND_HARDLINK",
    "KIND_SYMLINK",
    "iter_archive",
]
