"""Dropbox storage provider - downloads whatever a *public Dropbox shared
link* points at (the only thing a Poster record actually stores:
`dropbox_url`).

This is deliberately not a full Dropbox API integration: no OAuth app, no
access-token management, no folder listing or metadata API calls. Dropbox
shared links (https://www.dropbox.com/s/... or /scl/fi/.../fo/...) serve
Dropbox's web preview by default, but forcing the `dl=1` query parameter
makes Dropbox serve the raw file bytes instead - documented, standard
shared-link behavior that needs no credentials at all. Per the approved
architecture review, this is "enough to download files from stored Dropbox
links when possible" - everything the ZIP export feature needs - while
leaving a real API integration (needed for e.g. browsing a whole Dropbox
folder, or writing back to Dropbox) as clearly-separated future work: swap
or extend this one class without anything upstream (DownloadService,
archive_zip.py) needing to change.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from app.storage.providers.base import StorageError, StorageObject

_DROPBOX_HOST_RE = re.compile(r"(^|\.)dropbox\.com$", re.IGNORECASE)
_FILENAME_RE = re.compile(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?')


def _as_direct_download_url(url: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query["dl"] = "1"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _filename_from(response: httpx.Response, fallback_reference: str) -> str:
    match = _FILENAME_RE.search(response.headers.get("content-disposition", ""))
    if match:
        return match.group(1).strip()
    tail = urlsplit(fallback_reference).path.rsplit("/", 1)[-1]
    return tail or "download"


class DropboxStorageProvider:
    name = "dropbox"

    # A poster/notice is never legitimately huge; this guards a
    # misbehaving or unexpectedly large shared link from blowing up
    # memory/export size during a bulk ZIP export.
    max_bytes: int = 100 * 1024 * 1024
    timeout_seconds: float = 20.0

    def can_handle(self, reference: str) -> bool:
        return bool(_DROPBOX_HOST_RE.search(urlsplit(reference).netloc))

    def verify(self, reference: str) -> bool:
        """Cheap link-health check: True if the link resolves (HTTP 200)
        without downloading the file's contents - `client.stream()` only
        reads response headers until the body is actually iterated, so
        this never pulls the full file just to check it still works."""
        direct_url = _as_direct_download_url(reference)
        try:
            with httpx.Client(follow_redirects=True, timeout=self.timeout_seconds) as client:
                with client.stream("GET", direct_url) as response:
                    return response.status_code == 200
        except httpx.HTTPError:
            return False

    def fetch(self, reference: str) -> StorageObject:
        direct_url = _as_direct_download_url(reference)
        try:
            with httpx.Client(follow_redirects=True, timeout=self.timeout_seconds) as client:
                with client.stream("GET", direct_url) as response:
                    if response.status_code != 200:
                        raise StorageError(f"Dropbox returned HTTP {response.status_code} for this link")
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > self.max_bytes:
                            raise StorageError(
                                f"File exceeds the {self.max_bytes // (1024 * 1024)} MB export limit"
                            )
                    name = _filename_from(response, reference)
                    return StorageObject(name=name, size_bytes=len(content), content=bytes(content))
        except httpx.HTTPError as exc:
            raise StorageError(f"Could not reach Dropbox for this link: {exc}") from exc
