"""Tests for Settings.assert_secure_for_production - the startup guard that
refuses to run with known-insecure configuration when
OAP_ENVIRONMENT=production."""
from __future__ import annotations

import pytest

from app.core.config import Settings


def test_passes_outside_production():
    Settings(environment="development", secret_key="change-me-in-production").assert_secure_for_production()


def test_rejects_default_secret_key_in_production():
    settings = Settings(
        environment="production", secret_key="change-me-in-production",
        encryption_key="a" * 44, cors_allowed_origins=["https://example.gov.hk"],
    )
    with pytest.raises(RuntimeError, match="insecure default"):
        settings.assert_secure_for_production()


def test_rejects_short_secret_key_in_production():
    settings = Settings(
        environment="production", secret_key="short",
        encryption_key="a" * 44, cors_allowed_origins=["https://example.gov.hk"],
    )
    with pytest.raises(RuntimeError, match="too short"):
        settings.assert_secure_for_production()


def test_rejects_missing_encryption_key_in_production():
    settings = Settings(
        environment="production", secret_key="a-sufficiently-long-random-secret-key-value",
        encryption_key=None, cors_allowed_origins=["https://example.gov.hk"],
    )
    with pytest.raises(RuntimeError, match="OAP_ENCRYPTION_KEY"):
        settings.assert_secure_for_production()


def test_rejects_wildcard_cors_in_production():
    settings = Settings(
        environment="production", secret_key="a-sufficiently-long-random-secret-key-value",
        encryption_key="a" * 44, cors_allowed_origins=["*"],
    )
    with pytest.raises(RuntimeError, match="CORS"):
        settings.assert_secure_for_production()


def test_accepts_properly_configured_production_settings():
    settings = Settings(
        environment="production", secret_key="a-sufficiently-long-random-secret-key-value",
        encryption_key="a" * 44, cors_allowed_origins=["https://example.gov.hk"],
    )
    settings.assert_secure_for_production()  # must not raise
