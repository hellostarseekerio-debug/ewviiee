"""Local-filesystem storage provider - reads a file already living under
one of this platform's own storage roots (import/archive/export, or an
optional Dropbox/Drive/OneDrive sync root). Reuses the same path-traversal
guard (`resolve_within_root`) used everywhere else a path reaches the
filesystem from outside code, per app/core/file_safety.py."""
from __future__ import annotations

from pathlib import Path

from app.core.file_safety import UnsafeFileError, resolve_within_root
from app.storage.providers.base import StorageError, StorageObject


class LocalStorageProvider:
    name = "local"

    def __init__(self, allowed_roots: list[Path]) -> None:
        self._allowed_roots = allowed_roots

    def can_handle(self, reference: str) -> bool:
        return not reference.startswith(("http://", "https://"))

    def fetch(self, reference: str) -> StorageObject:
        try:
            path = resolve_within_root(Path(reference), self._allowed_roots)
        except UnsafeFileError as exc:
            raise StorageError(str(exc)) from exc
        if not path.is_file():
            raise StorageError(f"File not found: {reference}")
        content = path.read_bytes()
        return StorageObject(name=path.name, size_bytes=len(content), content=content)
