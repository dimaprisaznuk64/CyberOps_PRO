# Дорожня карта CyberOps PRO

> Цей файл — постійна памʼять плану для наступних сесій. Оновлюй після кожного
> завершеного етапу: статус, комеїти, наступні кроки.

## Статус версій

| Версія | Статус | Що входить | Комміт |
|---|---|---|---|
| v0.1 | ✅ | FastAPI, PostgreSQL, Alembic, JWT, RBAC, auth, Docker | (історія) |
| v0.2 | ✅ | Redis, Celery, worker, Nmap-сканер, assets, scans, етичний guard | |
| v0.3 | ✅ | Nmap-parser (CPE), services, findings, risk score | |
| v0.4 | ✅ | RabbitMQ-події, notifications, reports, audit logs | |
| v0.5 | ✅ | WebSocket, real-time dashboard, E2E-тести | |
| v0.6 | ✅ | Prometheus, Grafana, structured logs, OpenTelemetry | |
| v0.7 | ✅ | Microservices + API Gateway (edge JWT, identity headers, ws-relay) | `d862578` |
| v0.8 | ✅ | Kubernetes (kustomize), CI/CD (GHCR, kind E2E, kustomize-валідація) | `8ab49e6` |
| v0.9 | ✅ | Terraform/AWS (EC2 + SG + EIP + user-data deploy) | `b5966bd` |
| v1.0 | ✅ | Security Lab, AI Assistant, docs+demo, **Frontend (Next.js)** | `ac4dab3`, `a8fda16`, `fced99e`, `2244dae` |
| v1.1 | ✅ | Канали сповіщень: Email (SMTP), Telegram, налаштування в UI | (поточний) |
| v1.2 | ✅ | App Security: rate limiting, security headers, TLS, CI-сканування, 18 CVE | (поточний) |

## Фікси після введення в експлуатацію

- `dcf3a56` — frontend: `/health` повертає `services` словником, не масивом → render `Object.entries`.
- `8500c07` — worker: SQLAlchemy async-пул не можна перевикористовувати між Celery-тасками (`asyncio.run` на кожен таск) → окремий engine з `NullPool`. Симптом: «Task attached to a different loop» на 2-му сканi, scan зависає у `pending`.

## Відомі незакриті пункти плану (наступні пріоритети)

- **#14 Notifications канали** — ✅ закрито у v1.1:
  - `notifications.channel` (`web`/`email`/`telegram`) + `status`/`destination`/`sent_at`/`error`
    (міграція `0006_notification_channels`); fan-out у worker, доставка — окремий Celery-таск
    `workers.tasks.deliver_notification`, лічильник `notifications_delivered_total`;
  - Email через SMTP (text+HTML, екранування, TLS/SSL, auth) і Telegram через Bot API
    (HTML, екранування, обрізання до ліміту);
  - поріг `NOTIFY_MIN_SEVERITY` як серверна підлога + персональний поріг користувача
    (`effective_min_severity` = найсуворіший);
  - API: `GET`/`PATCH /notifications/preferences`, `POST /notifications/test`,
    `POST /notifications/{id}/retry`, `?channel=` фільтр;
  - UI: форма каналів у Settings, бейджі каналу/доставки + «Повторити» у Notifications;
  - інфра: mailpit-профіль у compose, anchor `x-notify-environment`, k8s configmap/secret
    (+ `secretRef` у worker — без нього доставка не мала б паролів);
  - 31 тест (`tests/test_notification_channels.py`), всього 104.
- **#16 App Security** — ✅ закрито:
  - rate limiting на Gateway (`gateway/ratelimit.py`, token bucket у пам'яті):
    login/register/refresh/change-password — 5/хв за IP, решта API — 120/хв за
    `sub` токена (анонімні — за IP, щоб не ділив ліміт весь NAT);
    `429` + `Retry-After` + `X-RateLimit-*`, метрика `gateway_rate_limited_total`;
    `/health` і `/metrics` не обмежені, ліміт не витікає через 401 (перевірка
    токена раніше за ліміт); ключі чистяться, щоб ротація IP не роздувала пам'ять;
  - security headers: суворий CSP (`default-src 'none'`) для API, окремий для
    legacy `/dashboard` (там інлайновий скрипт), HSTS, `nosniff`, `DENY`,
    `no-referrer`, COOP, Permissions-Policy;
  - TLS на gateway через `gateway/entrypoint.sh` (TLS 1.2+, сучасні ciphers) —
    за замовчуванням HTTP, бо TLS термінує балансувальник;
  - CI: новий job `security` — Bandit (`-ll`, чисто), pip-audit (жорсткий gate),
    Trivy (поки non-blocking), Semgrep (за наявності токена);
  - знайдено й виправлено 18 CVE: fastapi `0.115 → 0.141`, starlette `0.46 → 1.7`
    (без явного pin FastAPI тягнув би вразливу транзитивну), `python-jose → PyJWT`
    (jose не підтримується, тягнув CVE в `ecdsa`), `pytest 8 → 9`;
  - `JWT_SECRET` >= 32 байт (PyJWT попереджав про 20-байтний дефолт) + відмова
    стартувати з шаблонним секретом у `APP_ENV=production`;
  - nmap-XML тепер через `defusedxml` (XML залежить від відповідей цілі);
  - 22 тести (`tests/test_ratelimit.py`, `tests/test_jwt_secret.py`), всього 127.
- **#21 Jaeger** — OpenTelemetry-експортер OTLP вже є в коді (`TRACING_ENABLED`, `OTLP_ENDPOINT`), але Jaeger не в compose/terraform. Додати `jaeger` сервіс до compose (16686 UI, 4318 OTLP HTTP) + scrape/настройка.

## Ідеї / дрібниці (не обовʼязково)

- Почистити завислий `pending`-скан (старий баг працює тільки до фікса; для чистоти — переведення у `failed` по таймауту).
- Перенести старий `frontend/index.html` у окрему теку legacy, щоб не мішати Next.js.
- Архів deep Nmap-результатів (raw_xml) з візуалізацією у `scans/[id]`.
- Додати віджет ризику для asset (сумативний з усіх сканів).
- `docker compose` для frontend: підтримати `NEXT_PUBLIC_API_URL` як build-arg (вже є) і задокументувати remote-розгортання (terraform + CORS).

## Корисні команди для наступних сесій

```bash
cd "C:/Users/DIMAS/Desktop/Programming/PythonPRO/CyberOps_PRO"
docker compose up -d --build            # весь стек + lab окремо:
docker compose -f security-lab/docker-compose.yml up -d --build
python scripts/demo.py --host test-db   # E2E демо через Gateway
docker compose --profile mail up -d      # локальний SMTP-стенд (пошта на :8025)
python -m ruff check app tests ../workers ../services ../gateway   # backend/.venv
cd backend && python -m pytest tests -q # тести (127)
cd frontend && npm run build && npx tsc --noEmit
cd backend && python -m bandit -r app ../gateway ../workers ../services -ll   # SAST
cd backend && python -m pip_audit -r requirements.txt                        # CVE
```