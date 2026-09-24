from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    worker_metrics_port: int = 9091

    scan_allow_public: bool = False
    nmap_timeout_seconds: int = 300

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    default_role: str = "user"

    cors_origins: str = "*"

    admin_username: str = "admin"
    admin_password: str = "admin"

    ai_provider: str = ""
    ai_model: str = "gpt-4o-mini"
    ai_base_url: str = "http://localhost:11434/v1"
    ai_api_key: str = ""
    ai_timeout_seconds: float = 30.0


settings = Settings()
