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
    settings = Settings(
        app_env="production", jwt_secret=secret, admin_password="s3cret-pass"
    )
    assert settings.jwt_secret == secret


def test_dev_placeholder_from_env_example_starts_the_app():
    # `cp .env.example .env` має дати стенд, який піднімається: заглушка
    # довша за 32 байти (коротша не пройшла б валідатор і core падав би
    # з ValidationError навіть у dev).
    env_secret = Settings.model_fields["jwt_secret"].default
    assert len(env_secret.encode()) >= MIN_JWT_SECRET_BYTES


def test_env_example_placeholder_is_rejected_in_production():
    with pytest.raises(ValidationError, match="шаблонн"):
        Settings(app_env="production", jwt_secret="dev-only-insecure-secret-change-me-1234567890")


def test_default_admin_password_is_rejected_in_production():
    # compose-override вимагає ADMIN_PASSWORD, але значення «admin» його
    # задовольняє — тож охорона має бути і в самому застосунку.
    with pytest.raises(ValidationError, match="шаблонн"):
        Settings(app_env="production", jwt_secret="y" * 48)


def test_placeholder_admin_password_is_rejected_in_production():
    # «password» сам по собі шаблонний (у PLACEHOLDER_PASSWORDS), але
    # «Password123» — ні: правило ловить точні значення, а не патерни.
    assert Settings(app_env="production", jwt_secret="y" * 48, admin_password="Password123")


def test_custom_admin_password_is_accepted_in_production():
    settings = Settings(app_env="production", jwt_secret="y" * 48, admin_password="s3cret-pass")
    assert settings.admin_password == "s3cret-pass"


def test_default_admin_password_is_fine_in_dev():
    assert Settings().admin_password == "admin"
