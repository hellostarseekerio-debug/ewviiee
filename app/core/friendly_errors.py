"""Translates technical exception messages into plain-language text
suitable for non-technical office staff.

Where a stage handler deliberately raises `WorkflowStageError` with a
clear, specific message (e.g. "Missing required field: estate"), that
message is already meant to be read by an end user and is left untouched.
This module exists for the *other* case: an unexpected, unhandled
exception (a network hiccup, a missing file, a full disk) that would
otherwise surface a raw Python/OS error like
"[Errno 111] Connection refused" or "FileNotFoundError: ...". The
technical detail is always still logged in full server-side
(`data/logs/application.log`) - this only changes what a user sees on
screen.
"""
from __future__ import annotations

import re

# Ordered (first match wins) list of (pattern, friendly message template).
# `{detail}` is replaced with the original technical message.
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"connection refused|connectionerror|failed to establish a new connection", re.I),
        "Could not reach a required service (such as the AI assistant or a network drive). "
        "Check your network connection and try again, or contact your administrator if this continues.",
    ),
    (
        re.compile(r"timed? ?out|timeout", re.I),
        "The operation took too long and was stopped. This can happen with a slow network "
        "connection or a very large file. Please try again.",
    ),
    (
        re.compile(r"no such file or directory|filenotfounderror|not found:", re.I),
        "A required file could not be found. It may have been moved, renamed, or deleted. "
        "Please check the file still exists and try again.",
    ),
    (
        re.compile(r"permission denied|permissionerror|access is denied", re.I),
        "The system does not have permission to read or write a required file. "
        "Please contact your administrator to check folder permissions.",
    ),
    (
        re.compile(r"no space left on device|disk quota exceeded|out of disk", re.I),
        "There is not enough storage space to complete this action. "
        "Please contact your administrator - the server's disk needs attention.",
    ),
    (
        re.compile(r"database is locked|operationalerror", re.I),
        "The system is temporarily busy. Please wait a moment and try again.",
    ),
    (
        re.compile(r"jsondecodeerror|expecting value", re.I),
        "The AI assistant returned a response the system could not understand. "
        "The document was processed using the standard rules instead.",
    ),
    (
        re.compile(r"memoryerror", re.I),
        "This file is too large or complex to process on this machine. "
        "Please contact your administrator.",
    ),
    (
        re.compile(r"corrupt|invalid pdf|unable to open", re.I),
        "This document appears to be damaged or is not a valid file of its type. "
        "Please re-scan or re-export the original document and try again.",
    ),
]

_FALLBACK = "Something went wrong while processing this document. Technical detail: {detail}"


def humanize_error(message: str) -> str:
    """Returns a plain-language version of a technical error message,
    always preserving the original as a "Technical detail" suffix so an
    administrator (or a curious user) can still see exactly what happened
    and search for it in the logs."""
    if not message:
        return "An unknown error occurred. Please contact your administrator."

    for pattern, friendly in _PATTERNS:
        if pattern.search(message):
            return f"{friendly} (Technical detail: {message})"

    return _FALLBACK.format(detail=message)
