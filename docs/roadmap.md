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
| v1.3 | ✅ | Jaeger: OTLP-трейси для core/auth/worker, скрейп, Grafana-датасорс | `3dd1870` |
| v1.4 | ✅ | Завислі скан: 503 при недоступному брокері + celery beat-збирач | (поточний) |
| v1.5 | ✅ | Архів сирого Nmap-XML: gzip у БД, /raw + /raw.xml, «deep»-парсер, панель у UI | (поточний) |
| v1.6 | ✅ | Агрегований ризик активу: поточний + історичний максимум, сортування в UI | (поточний) |

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
- **#21 Jaeger** — ✅ закрито:
  - `jaeger` (all-in-one 1.62) у compose: UI `:16686`, OTLP/HTTP `:4318`;
    у k8s — Deployment + Service (NodePort 30086);
  - `OTLP_ENDPOINT` у compose перекривається на `http://jaeger:4318/v1/traces`
    (окрема змінна `OTLP_ENDPOINT_INTERNAL`, бо host-`.env` з `localhost`
    у контейнері вказує на сам контейнер);
  - `TRACING_SERVICE_NAME` проставляється per-service (core/auth/worker) — без
    `Resource.service.name` Jaeger згрупував би все в `unknown_service`;
  - воркер тепер реально експортує спани: `init_tracing()` при імпорті
    `workers/celery_app.py` (раніше `get_tracer()` давав no-op і `scan.run`
    зникав);
  - Prometheus скрейпить `jaeger:14269`, в Grafana додано Jaeger-датасорс
    (+`uid: prometheus`, щоб працював `tracesToLogsV2`);
  - `init_tracing()` ідемпотентна (OTel забороняє перевизначати глобальний
    провайдер), `get_tracer()` бере трасер із нашого провайдера;
  - 6 тестів (`tests/test_tracing.py`) з `InMemorySpanExporter`, всього 133.

## Ідеї / дрібниці (не обовʼязково)

- **Архів сирого Nmap-XML** — ✅ закрито у v1.5:
  - `services/scanner/nmap_runner.py` тепер не викидає «deep»-шари: версія й
    аргументи nmap, `scaninfo` (`numservices`, не `services`), усі hostname'и,
    OS-відпечатки з точністю, NSE-вивід (хостів і портів, обрізаний до 4000
    символів + 50 елементів), `uptime`/`distance`, `runstats`. Старі ключі
    (`command`, `hosts[].hostname`) збережено — з ними працюють analysis і тести;
  - база: `raw_xml` (plain Text) замінено на `raw_xml_gz` (LargeBinary, gzip,
    `mtime=0` для детермінованих байтів) — міграція `0007_scan_raw_archive`.
    Стара колонка лишається: читання з неї підтримано для існуючих сканів,
    нових записів у ній немає;
  - `app/services/raw_nmap.py`: pack/unpack + метадані. Розмір і SHA-256
    рахуються з реальних байт, а не з окремої колонки — дубльоване значення
    рано чи пізно розійшлося б із вмістом доказу;
  - API: `GET /scans/{id}/raw` (метадані + deep-розбір, `?include_xml=false`,
    `truncated` якщо XML більший за `SCAN_RAW_XML_MAX_CHARS`) і
    `GET /scans/{id}/raw.xml` (download). `raw_xml` прибрано зі
    `ScanResultOut` — інакше кожне відкриття сторінки тягне сотні кілобайт;
    ендпоинти без архіву роблять `defer(raw_xml, raw_xml_gz)`;
  - битий gzip -> 500 на архіві, але сам скан лишається доступним;
  - UI: `components/ScanRawArchive.tsx` — метадані, картки хостів з OS/NSE,
    «Завантажити .xml» (через blob, бо `<a href>` не несе Authorization) і
    «Показати сирий XML» за кліком; `.codeblock` у globals.css;
  - 11 тестів (`tests/test_scan_raw_archive.py`) + 4 на парсер, всього 163.
- **Віджет ризику для asset** — ✅ закрито у v1.6:
  - `app/services/asset_risk.py`: агрегат рахується з `scans` (окремої колонки
    в `assets` немає — воно б розпадалося з кожним сканом). Два запити на весь
    список активів, без N+1;
  - показуємо і поточний стан (останнє `done` сканування), і `max_risk_*` за
    історію: стара вразливість не повинна зникати з виду, але й застарілі
    знахідки не мають видаватися за поточні;
  - `row_number() over (partition by asset_id order by finished_at desc, id desc)`:
    id — tiebreaker, бо повторний скан нерідко має той самий `finished_at`;
  - рівень рахується тим самим `risk_level_from_score`, що й для сканування;
  - `scans_count` рахує всі спроби ( і `failed`), `last_scan_at` — `max(finished_at)`,
    тож видно й невдалі сканування;
  - `AssetOut` доповнений полями; `POST`/`PATCH` теж їх повертають, інакше
    бейдж зникав би до перезавантаження;
  - рахуються всі сканування активу, а не лише власні: чужий актив не можна
    сканувати, а бачити його аналітик може так само, як власник;
  - UI: колонки «Ризик»/«Історія»/«Скани», сортування за ризиком/назвою/ID,
    непросканований актив — сірий «не скановано» (RiskPill для `null` показував
    би LOW, тобто вигаданий безпечний стан);
  - 7 тестів (`tests/test_assets.py`), всього 170.
- **`docker compose` для frontend** — підтримати `NEXT_PUBLIC_API_URL` як
  build-arg (вже є) і задокументувати remote-розгортання (terraform + CORS).
- **Завислі скан** — ✅ закрито у v1.4:
  - корінь проблеми: `create_scan` комітив рядок у БД і лише потім робив
    `enqueue()`; при недоступному брокері API падав у 500, а рядок лишався
    `pending` назавжди. Тепер `except` -> `mark_enqueue_failed()` + `503`;
  - `app/services/scans.py`: `fail_stale_scans()` переводить у `failed`
    `pending`/`running` без `finished_at` старші за `SCAN_STALE_AFTER_SECONDS`
    (для running орієнтир — `started_at`), з tolerant-обробкою naive datetime;
  - `workers.tasks.reap_stale_scans` + celery beat (`-B` у Dockerfile CMD),
    інтервал `SCAN_REAPER_INTERVAL_SECONDS`;
  - 5 тестів (`tests/test_scan_reaper.py`) + тест на 503, всього 138.
- **Gateway в трасі** — ✅ закрито у v1.3:
  - `gateway/tracing.py`: самостійний (gateway живе в окремому образі)
    TracerProvider + FastAPI- і **httpx**-інструментація, тож тепер видно
    ланцюг `gateway (server) → httpx GET (client) → core (server)`, а
    `traceparent` прокидається вгору — одна траса на весь запит;
  - `/metrics` і `/health` виключені через `excluded_urls`: інакше скрейп
    раз на 15с давав би ~5.7 тис. сміттєвих спанів на добу на сервіс
    (те саме додано й у `app/services/tracing.py`);
  - 6 тестів (`tests/test_gateway_tracing.py`) + 1 на виключення шуму;
    httpx-інструментація процесно-глобальна, тому тест на клієнтський спан
    мусить бути першим у модулі — інакше спани підуть у провайдер попереднього.
- **Legacy-дашборд у окремій теці** — ✅ закрито у v1.3:
  - `frontend/index.html` -> `legacy/dashboard/index.html` (Next.js його все одно
    ігнорував, але файл виглядав як частина застосунку);
  - знайшовся реальний баг: монтувався весь `frontend/`, а gateway не вимагає
    токен для `/dashboard`, тож публічно віддавалися `node_modules/`, `.env.example`,
    `next.config.mjs` і `.next/`. Тепер монтується лише `legacy/dashboard/`,
    а бекенд стартує без нього (warning замість падіння на imports);
  - `backend/Dockerfile` більше не копіює `frontend/` — образ менший;
  - 2 тести: сторінка віддається, решта шляхів каталогу — 404.

## Корисні команди для наступних сесій

```bash
cd "C:/Users/DIMAS/Desktop/Programming/PythonPRO/CyberOps_PRO"
docker compose up -d --build            # весь стек + lab окремо:
docker compose -f security-lab/docker-compose.yml up -d --build
python scripts/demo.py --host test-db   # E2E демо через Gateway
docker compose --profile mail up -d      # локальний SMTP-стенд (пошта на :8025)
python -m ruff check app tests ../workers ../services ../gateway   # backend/.venv
cd backend && python -m pytest tests -q # тести (170)
cd frontend && npm run build && npx tsc --noEmit
cd backend && python -m bandit -r app ../gateway ../workers ../services -ll   # SAST
cd backend && python -m pip_audit -r requirements.txt                        # CVE
```