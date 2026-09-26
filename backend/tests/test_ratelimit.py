from __future__ import annotations

import pytest

from gateway.config import settings
from gateway.headers import CSP_STATIC, CSP_STRICT, security_headers
from gateway.main import app as gateway_app
from gateway.ratelimit import BUCKET_API, BUCKET_AUTH, TokenBucketLimiter
from tests.conftest import login

# Ліміти ставимо вручну: тест має бути детермінованим, а не залежати від .env
AUTH_LIMIT = 3
API_LIMIT = 4


@pytest.fixture
def tight_limits():
    limiters = {
        BUCKET_AUTH: TokenBucketLimiter(AUTH_LIMIT, burst=AUTH_LIMIT),
        BUCKET_API: TokenBucketLimiter(API_LIMIT, burst=API_LIMIT),
    }
    gateway_app.state.limiters = limiters
    yield limiters
    gateway_app.state.limiters = None


# --- token bucket -----------------------------------------------------------


def test_bucket_allows_burst_then_blocks():
    limiter = TokenBucketLimiter(limit=3, burst=3)

    decisions = [limiter.check("ip:1.2.3.4", now=0.0) for _ in range(3)]
    assert all(d.allowed for d in decisions)
    assert decisions[0].remaining == 2
    assert decisions[-1].remaining == 0

    blocked = limiter.check("ip:1.2.3.4", now=0.0)
    assert blocked.allowed is False
    assert blocked.retry_after == 20  # 1 токен / (3 на хв) = 20 с
    assert blocked.limit == 3


def test_bucket_refills_over_time():
    limiter = TokenBucketLimiter(limit=3, burst=3)
    for _ in range(3):
        limiter.check("ip:1.2.3.4", now=0.0)

    # за 20 с накопичується рівно 1 токен
    assert limiter.check("ip:1.2.3.4", now=20.0).allowed is True
    assert limiter.check("ip:1.2.3.4", now=20.0).allowed is False


def test_bucket_refill_is_capped_at_burst():
    limiter = TokenBucketLimiter(limit=3, burst=3)
    for _ in range(3):
        limiter.check("ip:1.2.3.4", now=0.0)

    # через годину все одно тільки 3 токени, не 180
    for _ in range(3):
        assert limiter.check("ip:1.2.3.4", now=3600.0).allowed is True
    assert limiter.check("ip:1.2.3.4", now=3600.0).allowed is False


def test_buckets_are_isolated_per_key():
    limiter = TokenBucketLimiter(limit=1, burst=1)
    assert limiter.check("ip:1.1.1.1", now=0.0).allowed is True
    assert limiter.check("ip:1.1.1.1", now=0.0).allowed is False
    # сусідній IP не страждає
    assert limiter.check("ip:2.2.2.2", now=0.0).allowed is True


def test_bucket_prunes_stale_keys_to_avoid_unbounded_growth():
    limiter = TokenBucketLimiter(limit=1, burst=1, max_keys=10)

    for i in range(500):
        limiter.check(f"ip:10.0.0.{i}", now=float(i))
    # ротація IP не має накопичувати ключі нескінченно
    assert len(limiter._buckets) <= 10

    # старі ключі звільнили місце, але свіжий ключ із тієї ж ротації живий
    limiter.check("ip:10.0.0.499", now=500.0)
    assert len(limiter._buckets) <= 10


def test_reset_clears_state():
    limiter = TokenBucketLimiter(limit=1, burst=1)
    limiter.check("ip:1.1.1.1", now=0.0)
    limiter.reset()
    assert limiter.check("ip:1.1.1.1", now=0.0).allowed is True


def test_invalid_limit_rejected():
    with pytest.raises(ValueError):
        TokenBucketLimiter(limit=0)
    with pytest.raises(ValueError):
        TokenBucketLimiter(limit=5, window_seconds=0)


# --- інтеграція з gateway ---------------------------------------------------


async def test_login_is_rate_limited(client, tight_limits):
    for _ in range(AUTH_LIMIT):
        resp = await client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "wrong"}
        )
        assert resp.status_code == 401

    resp = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin1234"}
    )
    assert resp.status_code == 429
    assert resp.json()["detail"] == "Забагато запитів. Спробуйте пізніше."
    assert int(resp.headers["Retry-After"]) >= 1
    assert resp.headers["X-RateLimit-Limit"] == str(AUTH_LIMIT)
    assert resp.headers["X-RateLimit-Remaining"] == "0"


async def test_register_uses_the_same_auth_bucket(client, tight_limits):
    for i in range(AUTH_LIMIT):
        resp = await client.post(
            "/api/v1/auth/register", json={"username": f"victim{i}", "password": "password123"}
        )
        assert resp.status_code in (201, 409)

    resp = await client.post(
        "/api/v1/auth/register", json={"username": "lastone", "password": "password123"}
    )
    assert resp.status_code == 429


async def test_api_bucket_is_separate_from_auth(client, tight_limits):
    """Наповнюємо api-відро до нуля і переконуємось, що login все ще працює:
    це різні відра, інакше блокований клієнт не зміг би увійти знову."""
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    for _ in range(API_LIMIT):
        assert (await client.get("/api/v1/notifications", headers=headers)).status_code == 200
    assert (await client.get("/api/v1/notifications", headers=headers)).status_code == 429

    # auth-відро недоторкане
    assert await login(client, "analyst", "analyst1234")


async def test_api_requests_are_limited_per_user(client, tight_limits):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    for _ in range(API_LIMIT):
        assert (await client.get("/api/v1/notifications", headers=headers)).status_code == 200

    blocked = await client.get("/api/v1/notifications", headers=headers)
    assert blocked.status_code == 429
    assert blocked.headers["X-RateLimit-Limit"] == str(API_LIMIT)

    # інший користувач має власний ліміт
    await client.post(
        "/api/v1/auth/register", json={"username": "viewer11", "password": "password123"}
    )
    other = await login(client, "viewer11", "password123")
    assert (
        await client.get(
            "/api/v1/notifications", headers={"Authorization": f"Bearer {other}"}
        )
    ).status_code == 200


async def test_health_and_metrics_are_not_rate_limited(client, tight_limits):
    for _ in range(API_LIMIT + 3):
        assert (await client.get("/health")).status_code in (200, 503)
        assert (await client.get("/metrics")).status_code == 200


async def test_limiter_can_be_disabled(client, tight_limits, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    for _ in range(AUTH_LIMIT + 3):
        resp = await client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "wrong"}
        )
        assert resp.status_code == 401


async def test_unauthorized_is_checked_before_the_limiter(client, tight_limits):
    """Без токена має бути 401, а не 429 — інакше ліміт витікає інформацію
    про те, що ендпоінт існує."""
    resp = await client.get("/api/v1/assets")
    assert resp.status_code == 401


# --- security headers -------------------------------------------------------


async def test_security_headers_present(client):
    resp = await client.get("/health")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert resp.headers["Content-Security-Policy"] == CSP_STRICT
    assert resp.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert "camera=()" in resp.headers["Permissions-Policy"]
    assert resp.headers["Strict-Transport-Security"] == (
        f"max-age={settings.hsts_max_age}; includeSubDomains"
    )


async def test_headers_on_api_responses_and_rate_limited_responses(client, tight_limits):
    for _ in range(AUTH_LIMIT):
        await client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "wrong"}
        )
    resp = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin1234"}
    )
    assert resp.status_code == 429
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["Content-Security-Policy"] == CSP_STRICT


def test_csp_relaxes_only_for_legacy_dashboard():
    assert security_headers("/dashboard")["Content-Security-Policy"] == CSP_STATIC
    assert security_headers("/api/v1/assets")["Content-Security-Policy"] == CSP_STRICT
    assert security_headers("/")["Content-Security-Policy"] == CSP_STRICT


def test_hsts_can_be_disabled(monkeypatch):
    monkeypatch.setattr(settings, "hsts_enabled", False)
    assert "Strict-Transport-Security" not in security_headers("/api/v1/assets")
