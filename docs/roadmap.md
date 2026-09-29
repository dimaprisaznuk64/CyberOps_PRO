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
| v1.7 | ✅ | Віддалене розгортання: порти лише gateway/UI, обов'язкові секрети, prod-override, SSH-тунель до метрик | (поточний) |
| v1.8 | ✅ | Закрито ескалацію через register + реальний сівач адміна | (поточний) |
| v1.9 | ✅ | Ownership у звітах + модель видимості даних задокументована | (поточний) |
| v1.10 | ✅ | Gateway: актуальний стек + виправлено Dockerfile і трейсинг | (поточний) |
| v1.11 | ✅ | Refresh-токен у тілі запиту замість query | (поточний) |
| v1.12 | ✅ | K8s: `DATABASE_URL`/`CORS_ORIGINS` у Secret, а не ConfigMap + інваріанти манифестів | (поточний) |

## Фікси після введення в експлуатацію

- `dcf3a56` — frontend: `/health` повертає `services` словником, не масивом → render `Object.entries`.
- `8500c07` — worker: SQLAlchemy async-пул не можна перевикористовувати між Celery-тасками (`asyncio.run` на кожен таск) → окремий engine з `NullPool`. Симптом: «Task attached to a different loop» на 2-му сканi, scan зависає у `pending`.
- **v1.7 (знайдено смоук-тестом на живому стенді)** — ворер кладав у `scans.raw_xml_gz` не байти, а `packed[0]`, тобто перший байт gzip (`0x1f` = 31). Запис падав (`a bytes-like object is required, not 'int'`), скан лишався `running` до reaper'а — тобто **кожне** сканування ламалося на реальному запуску, хоча CI був зелений: `test_scan_raw_archive.py` писав архів у БД руками, цю ділянку не виконуючи. Виправлено + 3 тести на реальний шлях воркера (`tests/test_worker_scan_archive.py`).
- **v1.7** — `cp .env.example .env` (документований крок) давав `JWT_SECRET` у 27 байт, а застосунок вимагає ≥32 → `core` падав на `ValidationError` ще з v1.2. Заглушка в `.env.example` подовжена до 45 байт і додана до `PLACEHOLDER_SECRETS`, тож dev піднімається, а production її відхиляє.
- **v1.7** — `admin_password` не мав жодної перевірки: compose-override вимагає змінну, але значення `admin` її задовольняє. Додано `PLACEHOLDER_PASSWORDS` і відмову в `APP_ENV=production` (6 тестів).

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
- **Віддалене розгортання (compose + terraform)** — ✅ закрито у v1.7:
  - `docker-compose.yml`: ззовні слухають лише `gateway:8000` і `frontend:3000`,
    решта (postgres, redis, rabbitmq, core, auth, prometheus, jaeger, grafana,
    mailpit) — на `127.0.0.1`. Локально нічого не змінюється, а на EC2
    дефолтний compose більше не відкриває `:5432` з `admin/admin` у інтернет.
    Метрики — через SSH-тунель (див. `observability_ssh_tunnel` в outputs);
  - `docker-compose.prod.yml` (override, `make up-prod`): секрети зроблені
    обов'язковими через `${VAR:?}` (JWT_SECRET, POSTGRES_PASSWORD,
    ADMIN_PASSWORD, CORS_ORIGINS, NEXT_PUBLIC_API_URL, GRAFANA_ADMIN_PASSWORD),
    `APP_ENV=prod`, `restart: unless-stopped` і ліміт логів `10m`×`3` на
    кожен сервіс (без ліміту json-file з'їдає диск t3.medium);
  - справжній баг у remote: `NEXT_PUBLIC_API_URL` вшивається в бандл під час
    збірки, тож фронтенд на сервері йшов у `localhost:8000` браузера
    відвідувача — UI порожній, симптом виглядає як зламаний бекенд. Тепер
    змінна обов'язкова + `scripts/remote-configure.sh` для перенаведення
    стенду на іншу адресу після EIP;
  - terraform: SG відкриває `3000` (без нього UI на EC2 був недістянний) і
    більше не відкриває `22` у `0.0.0.0/0` (`ssh_cidr` без дефолту);
    додано `admin_password` (required) і `app_public_url` (щоб обійти гонку
    з EIP, який доставляється після старту інстансу);
  - 5 тестів (`tests/test_compose_exposure.py`) на інваріанти «що світиться
    назовні» + обов'язковість секретів + 3 на шлях воркера до архіву, всього 184.
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

## v1.8 — закрито ескалацію через register + реальний сівач адміна

Знайдено під час смоук-тесту на живому стенді (не в тестах — вони були зелені).

- **P1 — публічна реєстрація дозволяла стати адміном.** `UserCreate.role` був
  вільним полем, а `validate_role` перевіряв лише «роль є у списку», тож запит
  `{"role": "admin"}` створював адміна без жодного доступу. Перевірено наживо:
  admin-токен + `GET /api/v1/users` (require_admin) відповідали 200.
  Тепер `role` прибрано зі схеми, а маршрут бере `ROLE_USER` з константи —
  значення з тіла запиту фізично не має шляху до колонки. У фронтенді
  прибрано dropdown ролі з форми реєстрації.
- **P2 — адміна в системі не існувало взагалі.** `ADMIN_USERNAME`/`ADMIN_PASSWORD`
  проходили через `.env` → compose → конфіг, але нікуди не читались: ні
  startup-хука, ні міграції з даними, ні CLI. Тому P1 була не «діркою поряд з
  адміном», а **єдиним** способом отримати адміна. Додано
  `app/services/seed.py::ensure_admin_user`, що викликається з `lifespan`
  auth-сервіса.
- **Ідемпотентність — головна вимога до сівача.** Пароль існуючого адміна ніколи
  не перезаписується, інакше кожен рестарт контейнера скидав би пароль, який
  адмін змінив через UI. Наявного користувача з тим самим ім'ям конфігурація
  до адміна **не** піднімає — інакше достатньо було б зареєструватися під іменем
  із `ADMIN_USERNAME` і дочекатися рестарту. Гонка двох реплік при старті
  обробляється через `IntegrityError`.
- **Тестів на це не було.** `test_auth.py` перевіряв `role: "user"`, а
  `test_users.py` — відкидання `superuser`; перевірки привілея не існувало.
  Додано `tests/test_admin_seed.py` (4 тести) і переписано
  `test_users.py::test_register_ignores_any_role` + додано
  `test_register_cannot_grant_admin_endpoints`. Всього 189.
- **Наслідок для клієнтів:** `scripts/demo.py` більше не може попросити
  `analyst` у реєстрації, тож тепер реєструє звичайного користувача і піднімає
  його до `analyst` через адміна (`PATCH /api/v1/users/{id}/role`) — саме той
  шлях, який єдиний доступний у системі. Кроків стало 8.

## v1.9 — ownership у звітах + модель видимості даних

Наступний пункт зі списку після v1.8. Знайдено при розборі розділу про reports.

- **`create_report` не перевіряв доступ до об'єкта.** Ендпойнт приймав `asset_id`
  або `scan_id` і збирав звіт без жодної перевірки — достатньо було знати ID
  чужого актива. Додано `_assert_report_target_allowed` у `routers/reports.py`.
- **Правила взяті з сусідніх ресурсів, щоб модель була послідовною:** актив — за
  `owner_id` (як в `assets.py:47`), сканування — за `created_by` (як в
  `scans.py:52-53`). Відповідь 404, а не 403, щоб не підтверджувати існування
  об'єкта.
- **Важливо: це не закривало живу діру для аналітика.** `build_asset_report` і
  `build_scan_report` викликаються лише з `create_report`, а той вимагає
  `require_analyst`. Тому для наявних ролей перевірка — не латка вразливості, а
  робота моделі явною. Справжня проблема була в тому, що модель ролей нігде не
  була описана і виглядала випадковою.
- **Модель видимості тепер задокументована** в README (таблиця по ресурсах).
  Ключове: аналітик бачить усі сканування, знахідки і звіти, але **не** бачить
  чужих активів — актив приватний для власника. Це свідоме рішення, а не баг.
- **Тести фіксують обидва боки моделі:** аналітик не може взяти звіт по чужому
  активу (404), але може — по чужому скану (201). Плюс 404 на неіснуючий об'єкт.
  Всього 192 тести.

## v1.10 — gateway: актуальний стек + виправлено Dockerfile і трейсинг

Наступний пункт зі списку. Тут виявилась не одна, а три проблеми, і дві з них
були неочевидними.

- **Gateway залишався на старому стеку.** `gateway/requirements.txt` тримав
  `fastapi==0.115` і `python-jose`, тоді як бекенд у v1.2 уже перейшов на
  `0.141`/`PyJWT` через CVE. Причому `python-jose` у коді взагалі не
  використовувався (код уже на PyJWT) — залежність просто забули прибрати.
  Приведено до одного стеку з бекендом: `fastapi==0.141`, явний pin
  `starlette==1.7` (та сама причина, що в бекенді), `pyjwt[crypto]==2`.
- **Dockerfile gateway не збирався взагалі.** `COPY gateway/ gateway/` —
  призначення відносне до WORKDIR `/gw`, тобто файли копіювалися в
  `/gw/gateway/`, а `chmod +x /gw/entrypoint.sh` і `ENTRYPOINT
  ["/gw/entrypoint.sh"]` вказували на шлях, якого не існувало. Збірка падала.
  **Наслідок серйозніший, ніж здається:** в стенді крутився старий образ,
  зібраний 2026-09-24, тобто **до v1.2**. Перевірка показала, що працюючий
  gateway не мав ні rate limiting, ні security headers, хоча в коді вони
  були — тобто вся security-робота v1.2 для gateway ніколи не була
  задеплоєна. Виправлено шляхи на `/gw/gateway/entrypoint.sh`.
- **Трейси gateway не експортувалися.** Gateway — єдиний сервіс, що в compose
  використовував `OTLP_ENDPOINT` (host-варіант з `.env` = `localhost:4318`),
  а не `OTLP_ENDPOINT_INTERNAL`, як core/auth/worker. Усередині контейнера
  `localhost` — це сам контейнер, тож у логах був Connection refused на
  `localhost:4318`. Цей баг пропустили у v1.3, коли решта сервісів перейшла на
  INTERNAL-варіант. Виправлено.
- **Перевірено наживо:** security headers (`X-Content-Type-Options`, DENY,
  CSP `default-src 'none'`, COOP, Permissions-Policy), rate limiting (5 запитів
  → 401, далі 429), трейси доходять до Jaeger (сервіси gateway + worker).
  192 тести, demo 8/8.

## v1.11 — refresh-токен у тілі запиту

Наступний пункт зі списку.

- **`POST /api/v1/auth/refresh` приймав токен як query-параметр.** Це означає, що
  довгоживучий refresh-токен (14 днів) потрапляє в URL, а URL — у логи проксі,
  access-логи та історію браузера. Токен тепер приймається з тіла запиту
  (схема `RefreshTokenRequest`).
- **Query-варіант більше не працює** — тест перевіряє, що такий запит
  отримує 422, а не токен. Це свідома відмова: клієнт, який надсилає токен
  у query, має отримати помилку, а не тиху успішну відповідь.
- **Тести:** 192 → 195 (refresh з тіла, відмова query, сміття → 401).

## v1.12 — K8s-конфіг був слабший за Docker-prod

Погляд на `infrastructure/kubernetes/` показав розбіжність із тим, що
v1.7 зробив для compose: у Docker-prod секрети обов'язкові, а K8s-база
лишилась з dev-значеннями в ConfigMap.

- **Пароль бази лежав у ConfigMap.** `DATABASE_URL` містить
  `cyberops:cyberops@postgres`, а ConfigMap не шифрований і читається будь-ким
  з `get configmaps`. Перенесено в `cyberops-secrets` — там, де вже лежать
  `POSTGRES_PASSWORD` і `JWT_SECRET`.
- **`CORS_ORIGINS` був `"*"`.** У compose-prod він обов'язковий (`:?`), а в
  K8s-базі — зірочка, тобто будь-який origin міг викликати API з браузера
  і читати відповіді з куки/токенів. Тепер у Secret, зі значенням для
  локального стенду; для продакшену overlay має перекрити його (або ключ
  прибирається — тоді не дозволений жоден origin, що й краще за зірочку).
- **Нотатка на секції secret:** значення в репозиторії — заглушки, для
  продакшену потрібен зовнішній менеджер (Secrets Manager, Vault, External
  Secrets, Sealed Secrets). Факт заглушок у Git — не сам по собі діра,
  але без нотатки через рік ніхто не зрозуміє, що це не справжні секрети.

### Регресія, яку це внесло

`kubectl kustomize` перевіряє синтаксис, а не семантику — тому перенесення
ключа в Secret пройшло CI зеленим і зламало **`migrations`** Job:
він мав лише `envFrom.configMapRef`, тому після перенесення `DATABASE_URL`
опинився без нього.

- **Помилка була тихою і неочевидною.** `app/config.py:28` має дефолт
  `postgresql+asyncpg://cyberops:cyberops@localhost:5432/cyberops`, тому
  Job не падав із «бракує змінної», а йшов в `localhost` усередині поду —
  тобто connection refused. `deploy.yml:34` чекає на `job/migrations`, тож
  пайплайн зупинявся б на таймауті, а не на зрозумілій помилці.
- **Виправлено:** `migrations.yaml` тепер імпортує і ConfigMap, і Secret.
- **Щоб цього не повторилось — 6 тестів** (`tests/test_k8s_manifests.py`):
  кожен app-контейнер (`core`/`auth`/`worker`/`gateway`/`migrations`) має
  обидва `envFrom`; `DATABASE_URL`/`CORS_ORIGINS` не повертаються в ConfigMap;
  `CORS_ORIGINS != "*"`; потрібні ключі є в Secret. Тест на `secretRef`
  перевірено у реверсі — він падає на незафіксованому `migrations.yaml`.
  Всього 211.

Перевірено: `kubectl kustomize infrastructure/kubernetes/overlays/dev`
збирається, у `migrations` приходять обидва джерела, 201 тест.

## Локальний стенд: порт Postgres на хості

Під час перевірки на живому стенді `docker compose up` впав не на логіці
застосунку, а на bind: `ports are not available ... 127.0.0.1:5432`. На
машині вже був локальний **PostgreSQL 18** — не наш контейнер. Інваріант із
v1.7 («сервіси слухають лише 127.0.0.1») працював як треба, але стенд через
це не піднімався взагалі.

- **Хардкод був у compose:** `127.0.0.1:5432:5432`. Тепер порт хоста —
  параметр `POSTGRES_PORT` (дефолт 5432), внутрішній лишається 5432. Тому
  `DATABASE_URL` правити не довелося: усередині мережі compose посилання
  йдуть на ім'я `postgres:5432`, а не на порт з мапінгу.
- **Значення в `.env` — локальне.** У CI/на чистій машині змінної немає,
  тож публікується дефолт 5432 і поведінка не міняється.
- **Тест на розбір підстановок пришлось перероби.** `test_compose_exposure`
  читає сирий YAML і ділить `ports` на `:` — а `${POSTGRES_PORT:-5432}`
  має двокрапку всередині фігурних дужок, тож рядок розпадався на п'ять
  частин і тест падав на синтаксисі. Тепер `_substitute()` розбирає
  `${VAR}`, `${VAR:-d}`, `${VAR-d}`, `${VAR:?err}`. Різниця `-` і `?`
  не косметична: `-` це дефолт, а `?` — вимога задати змінну, тож
  підставляти текст помилки в порт не можна.
- **Плюс 2 тести** (розбір підстановок + postgres публікує лише loopback
  із внутрішнім 5432), всього 203. Обидва перевірено у реверсі: на
  `5432:5432` без `127.0.0.1` падають.

## Перший запуск CI: воркфлою не парсилися, потім три справжні баги

Проєкт жив локально і жодного разу не був на GitHub. `gh repo create` →
перший пуш → усі три воркфлою впали за 0с з «This run likely failed
because of a workflow file issue». Це виглядало як особливість першого
пушу, але run без жодного кроку не перезапускається («cannot be retried»),
тож помилку треба було дістати іншим способом — через `workflow_dispatch`,
який і сам віддачив текст:

```
ci.yml:94      Unrecognized named-value: 'secrets'
docker.yml:20  Unrecognized function: 'lower'
```

**Ланцюг помилок — кожна наступна ховалася за попередньою:**

1. **`secrets` у кроковому `if`.** Контекст недоступний на цьому рівні,
   тож Semgrep-умова не парсилася. Secret перенесено в `env` рівня job.
   Побічно виправилось і реальне: Semgrep тепер і справді отримує токен,
   а не лише перевіряв його наявність.
2. **`lower()` не існує** в мові виразів GitHub (є `contains`, `format`,
   `join`, `hashFiles`). Регістр для GHCR тепер знижується через `tr`.
   Зверніть увагу: GHCR відхиляв би тег з великими літерами, тобто крок
   був зламаний не лише на розборі, а й на самому пуші образів.
3. **`setup-trivy@v0.2.3` не існує** — доступні `v0.2.6`, `v0.3.0`, `v0.3.1`.
   Job `security` падав на «Set up job» ще до Bandit. А версія Trivy
   `v0.58.2` теж виявилась не релізом (лише тегом), тож тепер `v0.70.0` —
   перша з реальним `release`.
4. **`kind load` не знаходив кластер.** `kind-action` за замовчуванням
   створює `chart-testing`, а `kind load` без `--name` читає контекст
   `kind`. Імʼя тепер задано явно.

**Далі `kubectl apply` показав те, що `kustomize` принципово не бачить:**

- **`jaeger.yaml`: `nodePort` без `type: NodePort`.** Service лишався
  ClusterIP, а apiserver відхиляв `spec.ports[1].nodePort: Forbidden`.
  Ключова деталь: відхиляється весь apply, тож разом із усіма іншими
  ресурсами маніфесту — однією помилкою зупиняється весь розгортання.
- **ConfigMap із ключами `datasources/datasource.yaml`.** Ключ ConfigMap не
  може містити `/` (regex `[-._a-zA-Z0-9]+`). Kustomize таке дозволяє, тож
  помилка вилізає лише на застосуванні. Розділено на три ConfigMap по
  каталогах + `subPath` у `volumeMounts`.

**+3 тести** (`tests/test_k8s_manifests.py`) на семантику, яку не ловить
жоден синтаксичний перевіряч: `nodePort` без типу, слеш у ключах ConfigMap
(і в статичних, і згенерованих `configMapGenerator`). Кожен перевірено у
реверсі — на відкачених правках падають. Всього 211.

Урок: `kubectl kustomize` у CI дає хибну впевненість. Правило, що спрацює
тут — перевіряти те, що API реально відхиляє, на живому кластері (kind у
CI це вже дає), а регресії на семантику фіксувати тестами.

## Job migrations: `ValidationError` замість Alembic — і мертва охорона

Після поправок `kubectl apply` нарешті пройшов, і перший реальний E2E впав
на `Wait migrations`: чотири спроби, усі в `Error`. Логи показали, що Job
падає не в Alembic, а на імпорті `app.config`.

**Причина 1: секрет із 27 байтів.** `JWT_SECRET: change-me-in-production-now`
у k8s `secret.yaml` — це 27 байт, а HS256 вимагає ≥ 32. Валідатор з v1.2
давав `ValidationError` ще до `alembic upgrade`, тож Job падав, не торкаючись
бази. Замінено на 45-байтний шаблон, який лишається у списку шаблонних.

**Причина 2 (гірша): охорона була мертвою.** Перевірка шаблонних секретів
дивилася на `app_env == "production"`, але і `docker-compose.prod.yml`, і
k8s ConfigMap виставляють **`APP_ENV: prod`**. Тобто жоден реальний
прод-деплой ніколи не проходив цю перевірку — ані JWT, ані `admin/admin`.

- Чому не помітив CI: тести користувалися рядком `"production"`, тобто
  перевіряли не той значення, що є в прод-конфігах. Класичний випадок, коли
  тест і код живуть у своєму світі.
- Тепер `_is_production()` приймає і `production`, і `prod` (з
  нормалізацією регістру й пробілів — значення приходить із YAML/ENV).
- **+3 тести**: `prod` запускає охорону для обох секретів, `PROD ` з
  пробілом теж, і «корисна» властивість k8s-секрету: довший за 32 байти, тож
  dev-стенд піднімається, але production із ним не стартує. Перевірено у
  реверсі: на старій перевірці `== "production"` три з них падають.

**Побічний ефект, який довелось відкотити назад.** Після того як охорона
запрацювала, kind-стенд почав падати з тієї ж причини: base-конфіг має
`APP_ENV: prod` і працює на заглушках. Тому dev-overlay тепер перекриває
`APP_ENV` на `dev` через JSON-patch, а base лишається `prod` для
справжніх прод-оверлеїв. **+2 тести** фіксують обидві сторони — інакше
наступна сесія знову спіткнеться на «а чому падає стенд».

**+8 тестів, всього 211.** Локально відтворено точно: `docker run` з
`APP_ENV=prod` і заглушками віддає `2 validation errors`, без `APP_ENV` —
міграції проходять.

Перевірено на CI: `test` (211) і `frontend` зелені, `Docker` зібрав і
запушив образи в GHCR, `kubectl apply` проходить, kind вантажить образи.

## Корисні команди для наступних сесій
```bash
cd "C:/Users/DIMAS/Desktop/Programming/PythonPRO/CyberOps_PRO"
docker compose up -d --build            # весь стек + lab окремо:
docker compose -f security-lab/docker-compose.yml up -d --build
python scripts/demo.py --host test-db   # E2E демо через Gateway
docker compose --profile mail up -d      # локальний SMTP-стенд (пошта на :8025)
python -m ruff check app tests ../workers ../services ../gateway   # backend/.venv
cd backend && python -m pytest tests -q # тести (211)
cd frontend && npm run build && npx tsc --noEmit
cd backend && python -m bandit -r app ../gateway ../workers ../services -ll   # SAST
cd backend && python -m pip_audit -r requirements.txt                        # CVE
```