from __future__ import annotations

from pathlib import Path

import pytest
from app.config import MIN_JWT_SECRET_BYTES, Settings
from pydantic import ValidationError

yaml = pytest.importorskip("yaml", reason="PyYAML приходить з uvicorn[standard]")


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


def test_prod_shorthand_also_triggers_the_placeholder_guard():
    """Регресія, знайдена на kind-E2E: охорона з v1.2 була мертвою.

    Перевірка дивилася лише на app_env == "production", але і compose-prod, і
    k8s ConfigMap виставляють APP_ENV=prod. Тобто жоден реальний прод-деплой
    її не проходив, а старі тести цього не ловили — вони теж користувалися
    "production" замість значення з прод-конфігів.
    """
    with pytest.raises(ValidationError, match="шаблонн"):
        Settings(app_env="prod", jwt_secret="change-me-in-production-now-abcdefghij")

    with pytest.raises(ValidationError, match="шаблонн"):
        Settings(app_env="prod", jwt_secret="y" * 48)  # admin/admin


def test_prod_shorthand_is_case_and_space_insensitive():
    # Значення приходить із YAML/ENV, тож "Prod " з-пробілом не має
    # непомітно вимикати охорону.
    with pytest.raises(ValidationError, match="шаблонн"):
        Settings(app_env="  PROD ", jwt_secret="y" * 48)


def test_k8s_secret_placeholder_survives_length_but_not_production():
    """JWT_SECRET із k8s secret.yaml мусить бути >= 32 байт (інакше Job
    migrations падає в ValidationError ще до Alembic) і водночас лишатися
    шаблонним, щоб прод із ним не стартував."""
    k8s_secret = (
        Path(__file__).resolve().parents[2] / "infrastructure/kubernetes/base/secret.yaml"
    )
    secret = yaml.safe_load(k8s_secret.read_text(encoding="utf-8"))["stringData"]["JWT_SECRET"]
    assert len(secret.encode()) >= MIN_JWT_SECRET_BYTES, "короткий секрет не пройде валідатор"
    # Старт у dev має бути можливий (kind-стенд), у production — ні.
    assert Settings(app_env="dev", jwt_secret=secret)
    with pytest.raises(ValidationError, match="шаблонн"):
        Settings(app_env="prod", jwt_secret=secret)
