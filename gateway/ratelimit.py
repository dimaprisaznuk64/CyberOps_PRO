from __future__ import annotations

import time
from dataclasses import dataclass

BUCKET_AUTH = "auth"
BUCKET_API = "api"


@dataclass
class Bucket:
    tokens: float
    updated_at: float


@dataclass
class Decision:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int


class TokenBucketLimiter:
    """Token bucket окремо на ключ (IP або user id).

    Лічильник у пам'яті процесу, тобто розрахований на один інстанс gateway.
    Якщо gateway запущено кількома репліками, кожна рахує ліміт незалежно —
    тоді потрібен спільний бекенд (Redis), як у реальному rate limiting.
    """

    def __init__(
        self,
        limit: int,
        window_seconds: float = 60.0,
        burst: int | None = None,
        max_keys: int = 10_000,
    ) -> None:
        if limit <= 0:
            raise ValueError("limit має бути додатним")
        if window_seconds <= 0:
            raise ValueError("window_seconds має бути додатним")
        self._limit = limit
        self._window = window_seconds
        self._burst = burst if burst is not None else limit
        self._max_keys = max_keys
        self._refill_per_second = limit / window_seconds
        self._buckets: dict[str, Bucket] = {}

    @property
    def _idle_ttl(self) -> float:
        # скільки часу ключ може простоювати, доки його не варто чистити
        return self._window + self._burst / self._refill_per_second

    def _prune(self, now: float) -> None:
        """Прибирає мертві ключі, щоб словник не рів безмежно від ротації IP.

        Ротація IP — це звичайний інструмент атаки, тож ліміт на розмір
        словника тут не менш важливий, ніж сам ліміт запитів.
        """
        if len(self._buckets) <= self._max_keys:
            return
        stale = [key for key, b in self._buckets.items() if now - b.updated_at > self._idle_ttl]
        for key in stale:
            del self._buckets[key]
        # резервуємо одне місце під ключ, який додається одразу після prune
        overflow = len(self._buckets) - (self._max_keys - 1)
        if overflow > 0:
            oldest = sorted(self._buckets.items(), key=lambda kv: kv[1].updated_at)
            for key, _ in oldest[:overflow]:
                del self._buckets[key]

    def check(self, key: str, now: float | None = None) -> Decision:
        current = time.monotonic() if now is None else now
        self._prune(current)

        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = Bucket(tokens=float(self._burst), updated_at=current)
            self._buckets[key] = bucket

        elapsed = max(current - bucket.updated_at, 0.0)
        bucket.tokens = min(
            float(self._burst), bucket.tokens + elapsed * self._refill_per_second
        )
        bucket.updated_at = current

        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            return Decision(
                allowed=True,
                limit=self._limit,
                remaining=int(bucket.tokens),
                retry_after=0,
            )

        deficit = 1.0 - bucket.tokens
        retry_after = max(1, int(deficit / self._refill_per_second + 0.999))
        return Decision(allowed=False, limit=self._limit, remaining=0, retry_after=retry_after)

    def reset(self) -> None:
        self._buckets.clear()
