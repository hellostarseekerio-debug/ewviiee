"""Verifies application.log uses a size-bounded RotatingFileHandler (not
an unbounded FileHandler that would eventually fill the disk on a
long-running production deployment), and that configure_logging() is
idempotent so no caller can accidentally accumulate duplicate handlers
(each producing a duplicate copy of every log line, and holding one more
file descriptor open forever)."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

import app.core.logging_config as logging_config


def _count_file_handlers() -> int:
    return sum(
        1 for h in logging.getLogger().handlers if isinstance(h, RotatingFileHandler)
    )


def test_configure_logging_installs_a_rotating_file_handler():
    logging_config._configured = False
    logging.getLogger().handlers = [
        h for h in logging.getLogger().handlers if not isinstance(h, RotatingFileHandler)
    ]

    logging_config.configure_logging()

    assert _count_file_handlers() == 1
    handler = next(h for h in logging.getLogger().handlers if isinstance(h, RotatingFileHandler))
    assert handler.maxBytes == logging_config._LOG_MAX_BYTES
    assert handler.backupCount == logging_config._LOG_BACKUP_COUNT


def test_configure_logging_is_idempotent():
    logging_config._configured = False
    logging.getLogger().handlers = [
        h for h in logging.getLogger().handlers if not isinstance(h, RotatingFileHandler)
    ]

    logging_config.configure_logging()
    logging_config.configure_logging()
    logging_config.configure_logging()

    assert _count_file_handlers() == 1
