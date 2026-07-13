"""Storage provider abstraction: the callers that need file bytes (ZIP
export, download endpoints) never know or care whether a reference points
at a local file, a Dropbox shared link, or (later) Google Drive/OneDrive/S3
- they call DownloadService.fetch(reference) and get bytes back, or a
StorageError they can turn into a per-item "skipped" entry.

Deliberately whole-file-in-memory (`StorageObject.content: bytes`), not a
streaming/chunked Protocol: every file this platform's resources actually
reference (posters, office documents) is small (a scanned notice, a PDF
form) - never a multi-gigabyte object - so a streaming interface would be
speculative complexity with no real caller today. If a future provider
(e.g. S3) needs true streaming for large objects, that's a reason to widen
this Protocol then, not a reason to build it now.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class StorageObject:
    name: str
    size_bytes: int | None
    content: bytes


class StorageError(RuntimeError):
    """Raised when a provider can't fetch a reference (network failure,
    missing local file, revoked/expired link, size limit exceeded, etc.).
    Callers (see app/storage/archive_zip.py) turn this into a per-item skip
    recorded in the export's README/metadata, never a hard failure for the
    whole batch - one bad link must not sink an export of thousands of
    good ones."""


@runtime_checkable
class StorageProvider(Protocol):
    name: str

    def can_handle(self, reference: str) -> bool:
        """Whether this provider knows how to resolve `reference` (a
        Dropbox URL, a local path, ...). DownloadService tries providers in
        order and uses the first one that answers True."""
        ...

    def fetch(self, reference: str) -> StorageObject:
        """Returns the file's bytes + name. Raises StorageError on any
        failure - never returns partial/corrupt content silently."""
        ...
