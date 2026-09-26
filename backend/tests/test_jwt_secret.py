from __future__ import annotations

import pytest
from app.config import MIN_JWT_SECRET_BYTES, Settings
from pydantic import ValidationError


def test_default_secret_is_long_enough():
    assert len(Settings().jwt_secret.encode()) >= MIN_JWT_SECRET_BYTES


def test_short_secret_is_rejected():
    with pytest.raises(ValidationError, match="32"):
        Settings(jwt_secret="short-secret")


def test_placeholder_secret_is_rejected_in_production():
    with pytest.raises(ValidationError, match="шаблонн"):
        Settings(app_env="production", jwt_secret="dev-secret-change-me-before-production")


def test_generated_secret_is_accepted_in_production():
    secret = "x" * 48
    assert Settings(app_env="production", jwt_secret=secret).jwt_secret == secret
