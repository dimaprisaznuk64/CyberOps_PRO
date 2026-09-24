from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    auth_service_url: str = "http://localhost:8002"
    core_service_url: str = "http://localhost:8001"
    upstream_timeout_seconds: float = 30.0

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"

    cors_origins: str = "*"


settings = GatewaySettings()