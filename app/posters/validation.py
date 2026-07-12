"""Dropbox URL validation shared by the Poster Archive's manual create/edit
endpoints and the paste-text import path."""
from __future__ import annotations

from urllib.parse import urlparse


class InvalidDropboxUrlError(ValueError):
    """Raised when a value claiming to be a Dropbox link isn't one."""


def is_valid_dropbox_url(value: str) -> bool:
    if not value or not value.strip():
        return False
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    return host == "dropbox.com" or host.endswith(".dropbox.com")


def assert_valid_dropbox_url(value: str) -> None:
    if not is_valid_dropbox_url(value):
        raise InvalidDropboxUrlError(
            f"'{value}' is not a valid Dropbox URL - expected an http(s):// link to dropbox.com"
        )
