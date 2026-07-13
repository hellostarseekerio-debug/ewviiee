"""DownloadService: the one thing callers (ZIP export, future single-file
download endpoints) depend on. A caller passes a reference string (a
Dropbox URL, a local path - it doesn't know or care which) and gets file
bytes back; adding a new provider (Google Drive, OneDrive, S3) never
requires touching a caller, only registering the new provider here."""
from __future__ import annotations

from app.storage.providers.base import StorageError, StorageObject, StorageProvider

__all__ = ["DownloadService", "StorageError", "StorageObject", "build_default_download_service"]


class DownloadService:
    def __init__(self, providers: list[StorageProvider]) -> None:
        self._providers = providers

    def fetch(self, reference: str) -> StorageObject:
        for provider in self._providers:
            if provider.can_handle(reference):
                return provider.fetch(reference)
        raise StorageError(f"No storage provider can handle this reference: {reference}")


def build_default_download_service(settings) -> DownloadService:
    from app.storage.providers.dropbox import DropboxStorageProvider
    from app.storage.providers.local import LocalStorageProvider
    from app.workflow.runner import allowed_import_roots

    # Order matters: Dropbox's can_handle() is host-specific (only matches
    # dropbox.com URLs), so it's safe to try first; Local is the catch-all
    # for anything that isn't an http(s) URL.
    return DownloadService(
        [DropboxStorageProvider(), LocalStorageProvider(allowed_import_roots(settings))]
    )
