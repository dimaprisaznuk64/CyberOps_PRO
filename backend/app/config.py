from __future__ import annotations

from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# HS256 за RFC 7518 очікує >= 256 біт ключа; коротший секрет — це не помилка
# конфігурації, а реально слабка підписна база.
MIN_JWT_SECRET_BYTES = 32
PLACEHOLDER_SECRETS = {
    "dev-secret-change-me-before-production",
    "change-me-in-production-now",
    "change-me-in-prod",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    debug: bool = True
    log_json: bool = False

    database_url: str = "postgresql+asyncpg://cyberops:cyberops@localhost:5432/cyberops"

    celery_broker_url: str = "redis://localhost:6379/0"

    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    events_exchange: str = "cyberops.events"
    events_enabled: bool = True

    realtime_mode: str = "memory"
    realtime_channel: str = "cyberops:ws"

    tracing_enabled: bool = False
    otlp_endpoint: str = "http://localhost:4318/v1/traces"
    # Jaeger групує спани за service.name, тому кожен сервіс має назвати себе
    # інакше всі сліди злипаються в один «unknown_service».
    tracing_service_name: str = "core"
    app_version: str = "1.2.0"
    worker_metrics_port: int = 9091

    scan_allow_public: bool = False
    nmap_timeout_seconds: int = 300
    # Скільки символів сирого nmap-XML вкладати у JSON-відповідь архіву.
    # Більше — віддаємо лише метадані, а сам файл качається окремим запитом.
    scan_raw_xml_max_chars: int = 400_000
    # Скан вважається завислим, якщо довше за цей час не дійшов до finished_at.
    # Запас має перекривати nmap_timeout_seconds, інакше reaper вб'є ще живий скан.
    scan_stale_after_seconds: int = 900
    scan_reaper_interval_seconds: int = 60

    jwt_secret: str = "dev-secret-change-me-before-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    @field_validator("jwt_secret")
    @classmethod
    def _validate_jwt_secret(cls, value: str, info: Any) -> str:
        if len(value.encode()) < MIN_JWT_SECRET_BYTES:
            raise ValueError(
                f"JWT_SECRET має бути не коротше {MIN_JWT_SECRET_BYTES} байт для "
                f"{'HS256'}; зараз {len(value.encode())}. Згенеруйте: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        if info.data.get("app_env") == "production" and value in PLACEHOLDER_SECRETS:
            raise ValueError("JWT_SECRET досі є шаблонним — згенеруйте власний")
        return value

    default_role: str = "user"

    cors_origins: str = "*"

    admin_username: str = "admin"
    admin_password: str = "admin"

    ai_provider: str = ""
    ai_model: str = "gpt-4o-mini"
    ai_base_url: str = "http://localhost:11434/v1"
    ai_api_key: str = ""
    ai_timeout_seconds: float = 30.0

    # --- Канали сповіщень (email / telegram) ---
    # Аварійний вимикач усіх зовнішніх каналів
    notifications_enabled: bool = True
    # Базовий URL фронтенду — для посилань у листах і повідомленнях
    app_base_url: str = "http://localhost:3000"
    # Серверний поріг: зовнішній канал вмикається лише коли severity >= notify_min_severity
    notify_min_severity: str = "high"

    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "cyberops@localhost"
    smtp_from_name: str = "CyberOps PRO"
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    smtp_timeout_seconds: float = 10.0

    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_api_base: str = "https://api.telegram.org"
    telegram_timeout_seconds: float = 10.0
    telegram_max_message_length: int = 4096


settings = Settings()
