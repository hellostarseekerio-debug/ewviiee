"""Covers the storage provider abstraction (app/storage/providers/*,
app/storage/download_service.py) - the layer that lets ZIP export (and any
future caller) fetch file bytes without knowing whether a reference points
at a local file or a Dropbox shared link.
"""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from app.storage.download_service import DownloadService
from app.storage.providers.base import StorageError
from app.storage.providers.dropbox import DropboxStorageProvider, _as_direct_download_url
from app.storage.providers.local import LocalStorageProvider


# ---------------------------------------------------------------------------
# LocalStorageProvider
# ---------------------------------------------------------------------------


def test_local_provider_can_handle_plain_paths_not_urls():
    provider = LocalStorageProvider(allowed_roots=[Path("/tmp")])
    assert provider.can_handle("/tmp/x/file.pdf") is True
    assert provider.can_handle("https://www.dropbox.com/x") is False


def test_local_provider_fetches_file_within_root(tmp_path):
    root = tmp_path / "import"
    root.mkdir()
    f = root / "poster.pdf"
    f.write_bytes(b"%PDF-1.4 fake content")

    provider = LocalStorageProvider(allowed_roots=[root])
    obj = provider.fetch(str(f))
    assert obj.name == "poster.pdf"
    assert obj.content == b"%PDF-1.4 fake content"
    assert obj.size_bytes == len(obj.content)


def test_local_provider_rejects_path_outside_allowed_roots(tmp_path):
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"data")
    root = tmp_path / "import"
    root.mkdir()

    provider = LocalStorageProvider(allowed_roots=[root])
    with pytest.raises(StorageError):
        provider.fetch(str(outside))


def test_local_provider_missing_file_raises_storage_error(tmp_path):
    root = tmp_path / "import"
    root.mkdir()
    provider = LocalStorageProvider(allowed_roots=[root])
    with pytest.raises(StorageError):
        provider.fetch(str(root / "does-not-exist.pdf"))


# ---------------------------------------------------------------------------
# DropboxStorageProvider
# ---------------------------------------------------------------------------


def test_dropbox_provider_can_handle_dropbox_hosts_only():
    provider = DropboxStorageProvider()
    assert provider.can_handle("https://www.dropbox.com/scl/fi/abc/poster.pdf") is True
    assert provider.can_handle("https://dropbox.com/s/abc/poster.pdf") is True
    assert provider.can_handle("https://evil-dropbox.com.attacker.net/x") is False
    assert provider.can_handle("/some/local/path.pdf") is False


def test_as_direct_download_url_forces_dl_1():
    assert _as_direct_download_url("https://www.dropbox.com/s/abc/x.pdf?dl=0") == (
        "https://www.dropbox.com/s/abc/x.pdf?dl=1"
    )
    # No existing query string at all.
    assert _as_direct_download_url("https://www.dropbox.com/s/abc/x.pdf") == (
        "https://www.dropbox.com/s/abc/x.pdf?dl=1"
    )


def test_dropbox_provider_fetches_and_wraps_response(monkeypatch):
    class FakeResponse:
        status_code = 200
        headers = {"content-disposition": 'attachment; filename="poster.pdf"'}

        def iter_bytes(self):
            yield b"file-bytes-here"

    class FakeStreamContext:
        def __enter__(self):
            return FakeResponse()

        def __exit__(self, *a):
            return False

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def stream(self, method, url):
            assert "dl=1" in url
            return FakeStreamContext()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    provider = DropboxStorageProvider()
    obj = provider.fetch("https://www.dropbox.com/s/abc/poster.pdf?dl=0")
    assert obj.name == "poster.pdf"
    assert obj.content == b"file-bytes-here"


def test_dropbox_provider_raises_storage_error_on_non_200(monkeypatch):
    class FakeResponse:
        status_code = 404
        headers = {}

        def iter_bytes(self):
            return iter(())

    class FakeStreamContext:
        def __enter__(self):
            return FakeResponse()

        def __exit__(self, *a):
            return False

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def stream(self, method, url):
            return FakeStreamContext()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    provider = DropboxStorageProvider()
    with pytest.raises(StorageError):
        provider.fetch("https://www.dropbox.com/s/abc/missing.pdf")


def test_dropbox_provider_enforces_max_bytes(monkeypatch):
    class FakeResponse:
        status_code = 200
        headers = {}

        def iter_bytes(self):
            yield b"a" * 10

    class FakeStreamContext:
        def __enter__(self):
            return FakeResponse()

        def __exit__(self, *a):
            return False

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def stream(self, method, url):
            return FakeStreamContext()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    provider = DropboxStorageProvider()
    provider.max_bytes = 5  # smaller than the 10 bytes the fake response yields
    with pytest.raises(StorageError):
        provider.fetch("https://www.dropbox.com/s/abc/huge.pdf")


def test_dropbox_provider_wraps_network_errors(monkeypatch):
    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def stream(self, method, url):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx, "Client", FakeClient)
    provider = DropboxStorageProvider()
    with pytest.raises(StorageError):
        provider.fetch("https://www.dropbox.com/s/abc/x.pdf")


# ---------------------------------------------------------------------------
# DownloadService (provider dispatch)
# ---------------------------------------------------------------------------


class _StubProvider:
    def __init__(self, name, handles, result=None, error=None):
        self.name = name
        self._handles = handles
        self._result = result
        self._error = error

    def can_handle(self, reference):
        return self._handles

    def fetch(self, reference):
        if self._error:
            raise self._error
        return self._result


def test_download_service_dispatches_to_first_matching_provider():
    from app.storage.providers.base import StorageObject

    match = StorageObject(name="x", size_bytes=1, content=b"x")
    service = DownloadService([_StubProvider("a", handles=False), _StubProvider("b", handles=True, result=match)])
    result = service.fetch("anything")
    assert result is match


def test_download_service_raises_when_no_provider_matches():
    service = DownloadService([_StubProvider("a", handles=False)])
    with pytest.raises(StorageError):
        service.fetch("unhandled-reference")
