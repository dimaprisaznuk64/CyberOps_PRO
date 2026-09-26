from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

# TLS 1.2+ лише; SHA-1 та RC4/3DES прибрані (RFC 8996)
DEFAULT_TLS_CIPHERS = (
    "ECDHE+AESGCM:ECDHE+CHACHA20:ECDHE+AES256:ECDHE+AES128"
)


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    auth_service_url: str = "http://localhost:8002"
    core_service_url: str = "http://localhost:8001"
    upstream_timeout_seconds: float = 30.0

    jwt_secret: str = "dev-secret-change-me-before-production"
    jwt_algorithm: str = "HS256"

    cors_origins: str = "*"

    # --- Rate limiting (v1.1) ---
    rate_limit_enabled: bool = True
    # login/register/refresh: 5 запитів на хвилину з одного джерела
    auth_rate_limit_per_minute: int = 5
    auth_rate_limit_burst: int = 5
    # решта API: м'який ліміт, ключ — user id, а якщо немає токена — IP
    api_rate_limit_per_minute: int = 120
    api_rate_limit_burst: int = 120
    rate_limit_max_keys: int = 10_000

    # --- Security headers (v1.1) ---
    security_headers_enabled: bool = True
    hsts_enabled: bool = True
    hsts_max_age: int = 31_536_000

    # --- TLS (v1.1) ---
    # TLS термінується на gateway, якщо задано cert/key (див. entrypoint.sh).
    # У compose за замовчуванням лишається HTTP всередині мережі.
    gateway_tls_certfile: str = ""
    gateway_tls_keyfile: str = ""
    gateway_tls_keyfile_password: str = ""
    gateway_tls_version: int = 2  # ssl.TLSVersion: 2 = TLSv1_2, 3 = TLSv1_3
    gateway_tls_ciphers: str = DEFAULT_TLS_CIPHERS


settings = GatewaySettings()
