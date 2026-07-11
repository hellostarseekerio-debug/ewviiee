"""File upload / file-path safety utilities.

Two distinct threats are addressed here:

1. Path traversal - a client-supplied path (or filename) must never be
   allowed to resolve outside an approved root directory.
2. Malicious/incorrect uploads - extension allowlisting, size limits, and a
   lightweight magic-byte signature check (no external `libmagic` binary
   dependency, so this works identically on Windows/macOS/Linux) so a
   renamed executable can't masquerade as a PDF/image.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

# Minimal file-signature table: enough to catch "renamed .exe as .pdf" style
# spoofing without adding a native libmagic dependency to the desktop build.
_SIGNATURES: dict[str, list[bytes]] = {
    ".pdf": [b"%PDF-"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".tiff": [b"II*\x00", b"MM\x00*"],
    ".zip": [b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"],
    ".docx": [b"PK\x03\x04"],  # docx is a zip container
}

_DANGEROUS_EXTENSIONS = {
    ".exe", ".dll", ".bat", ".cmd", ".com", ".msi", ".sh", ".ps1", ".vbs",
    ".js", ".jar", ".scr", ".app", ".pkg", ".dmg",
}

_SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9_\-. ]+$")


class UnsafeFileError(ValueError):
    """Raised when an uploaded/imported file fails a safety check."""


def sanitize_filename(filename: str) -> str:
    """Strips any directory components and rejects filenames containing
    path-traversal sequences or unsafe characters."""
    name = Path(filename).name  # drops any leading directories
    if name in {"", ".", ".."} or "/" in filename or "\\" in filename:
        raise UnsafeFileError(f"Unsafe filename: {filename!r}")
    if not _SAFE_FILENAME_RE.match(name):
        raise UnsafeFileError(f"Filename contains disallowed characters: {filename!r}")
    return name


def generate_storage_filename(original_filename: str) -> str:
    """Never trust the client-supplied name for the on-disk path - keep the
    validated extension but generate a fresh random basename."""
    safe_name = sanitize_filename(original_filename)
    suffix = Path(safe_name).suffix.lower()
    return f"{uuid.uuid4().hex}{suffix}"


def assert_extension_allowed(filename: str, allowed_extensions: list[str]) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in allowed_extensions:
        raise UnsafeFileError(f"File extension '{suffix}' is not permitted")
    if suffix in _DANGEROUS_EXTENSIONS:
        raise UnsafeFileError(f"File extension '{suffix}' is explicitly blocked")
    return suffix


def assert_size_within_limit(size_bytes: int, max_bytes: int) -> None:
    if size_bytes > max_bytes:
        raise UnsafeFileError(
            f"File is {size_bytes} bytes, exceeding the {max_bytes} byte limit"
        )
    if size_bytes <= 0:
        raise UnsafeFileError("File is empty")


def assert_content_matches_extension(content: bytes, suffix: str) -> None:
    """Best-effort magic-byte check. Extensions without a known signature
    (e.g. none configured) are allowed through - this defends against the
    common "renamed executable" attack, not a full content scanner."""
    signatures = _SIGNATURES.get(suffix)
    if not signatures:
        return
    if not any(content.startswith(sig) for sig in signatures):
        raise UnsafeFileError(
            f"File content does not match its '{suffix}' extension (failed signature check)"
        )


def resolve_within_root(candidate: Path, allowed_roots: list[Path]) -> Path:
    """Resolves `candidate` and verifies it falls under one of `allowed_roots`.
    Raises UnsafeFileError (never silently narrows) if it escapes every root -
    this is the path-traversal guard for any endpoint that accepts a path
    string from a client."""
    resolved = candidate.expanduser().resolve()
    for root in allowed_roots:
        try:
            resolved_root = root.expanduser().resolve()
        except OSError:
            continue
        if resolved == resolved_root or resolved_root in resolved.parents:
            return resolved
    raise UnsafeFileError(
        f"Path '{candidate}' is outside all permitted import roots"
    )
