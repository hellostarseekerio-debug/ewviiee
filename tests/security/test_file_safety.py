from __future__ import annotations


import pytest

from app.core.file_safety import (
    UnsafeFileError,
    assert_content_matches_extension,
    assert_extension_allowed,
    assert_size_within_limit,
    generate_storage_filename,
    resolve_within_root,
    sanitize_filename,
)


def test_sanitize_filename_strips_directories():
    assert sanitize_filename("report.pdf") == "report.pdf"


def test_sanitize_filename_rejects_path_traversal():
    with pytest.raises(UnsafeFileError):
        sanitize_filename("../../etc/passwd")


def test_sanitize_filename_rejects_embedded_separators():
    with pytest.raises(UnsafeFileError):
        sanitize_filename("a/b.pdf")


def test_generate_storage_filename_is_unpredictable_and_keeps_extension():
    name1 = generate_storage_filename("secret.pdf")
    name2 = generate_storage_filename("secret.pdf")
    assert name1 != name2
    assert name1.endswith(".pdf")
    assert "secret" not in name1


def test_dangerous_extension_blocked_even_if_allowlisted():
    with pytest.raises(UnsafeFileError):
        assert_extension_allowed("virus.exe", [".pdf", ".exe"])


def test_extension_not_in_allowlist_rejected():
    with pytest.raises(UnsafeFileError):
        assert_extension_allowed("data.csv", [".pdf", ".png"])


def test_size_limit_enforced():
    with pytest.raises(UnsafeFileError):
        assert_size_within_limit(100, max_bytes=50)


def test_empty_file_rejected():
    with pytest.raises(UnsafeFileError):
        assert_size_within_limit(0, max_bytes=50)


def test_content_signature_mismatch_detected():
    with pytest.raises(UnsafeFileError):
        assert_content_matches_extension(b"MZ\x90\x00", ".pdf")


def test_content_signature_match_passes():
    assert_content_matches_extension(b"%PDF-1.7 rest of file", ".pdf")


def test_resolve_within_root_accepts_nested_path(tmp_path):
    root = tmp_path / "import"
    root.mkdir()
    nested = root / "sub" / "file.pdf"
    nested.parent.mkdir(parents=True)
    nested.write_bytes(b"data")

    resolved = resolve_within_root(nested, [root])
    assert resolved == nested.resolve()


def test_resolve_within_root_rejects_escape(tmp_path):
    root = tmp_path / "import"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("data")

    with pytest.raises(UnsafeFileError):
        resolve_within_root(outside, [root])


def test_resolve_within_root_rejects_dotdot_traversal(tmp_path):
    root = tmp_path / "import"
    root.mkdir()
    traversal_attempt = root / ".." / "secret.txt"

    with pytest.raises(UnsafeFileError):
        resolve_within_root(traversal_attempt, [root])
