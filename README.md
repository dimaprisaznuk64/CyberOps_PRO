# CyberOps Platform PRO

Платформа моніторингу власної інфраструктури: аутентифікація, RBAC,
управління цілями (assets), контрольоване сканування, аналіз ризиків,
web-dashboard.

> ⚠️ **Етичне правило:** сканування проводимо **тільки** власних машин,
> локальної мережі або спеціальних навчальних лабораторій (`security-lab/`).

## Статус версій

| Версія | Статус | Що входить |
|---|---|---|
| 0.1 | ✅ | FastAPI, PostgreSQL, Alembic, JWT, RBAC (admin/analyst/user), реєстрація/логін, користувачі, тести, Docker |
| 0.2 | ✅ | Redis, Celery, worker, Nmap-сканер, Targets, Scans, етичний guard (лише приватні адреси) |
| 0.3 | ✅ | Nmap-parser (CPE), Services, Findings, Risk Score |
| 0.4 | ✅ | RabbitMQ-події, Notifications, Reports, Audit Logs |
| 0.5 | ✅ | WebSocket, real-time dashboard, тести E2E |
| 0.6 | ✅ | Prometheus, Grafana, structured logs, OpenTelemetry |
| **0.7** | ✅ | Microservices, API Gateway |
| **0.8** | ✅ | Kubernetes (kustomize manifests), CI/CD (GHCR, kind E2E) |
| **0.9** | ✅ | Terraform/Cloud (AWS EC2 + docker compose deploy, SG, EIP) |
| **1.0** | ✅ | Security Lab ✅, AI Assistant ✅, документація ✅, demo ✅, Frontend (Next.js) ✅ |
| **1.1** | ✅ | Канали сповіщень: Email (SMTP) ✅, Telegram ✅, налаштування в UI ✅ |
| **1.2–1.5** | ✅ | App Security (18 CVE) ✅, Jaeger ✅, reaper завислих сканів ✅, сирий Nmap-архів ✅ |
| **1.6** | ✅ | Агрегований ризик активу: поточний + історичний максимум, бейджі в UI ✅ |
| **1.7** | ✅ | Віддалене розгортання: порти лише gateway/UI, обов'язкові секрети в prod, SSH-тунель до метрик ✅ |
| **1.8** | ✅ | Закрито ескалацію через register + реальний сівач адміна ✅ |
| **1.9** | ✅ | Ownership у звітах + задокументована модель видимості даних ✅ |
| **1.10** | ✅ | Gateway: актуальний стек (18 CVE), робочий Dockerfile, трейсинг ✅ |
| **1.11** | ✅ | Refresh-токен у тілі запиту замість query ✅ |
| **1.12** | ✅ | K8s: `DATABASE_URL`/`CORS_ORIGINS` у Secret, а не ConfigMap ✅ |
| **1.13** | ✅ | Kind-E2E знову зелений: `imagePullPolicy`, колізія `GATEWAY_PORT`, повтори міграцій, охорона `APP_ENV=prod`, логи в CI ✅ |
| **1.14** | ✅ | UI в k8s працює: адреса API в рантаймі, CORS для nodePort, сид адміна з повторами; E2E перевіряє поведінку, а не процеси ✅ |
| **1.15** | ✅ | Compose-prod: одноразові міграції в стеку, образ не прив'язаний до адреси збірки, окремий воркфлоу `Prod E2E` ✅ |
| **1.16** | ✅ | Спостережуваність під контролем: недоступний `jaeger:14269`, `jaeger` поза rollout-циклом, `admin/admin` у k8s-Grafana, а `core`/`auth` не відправляли жодного спана; E2E перевіряє моніторинг ✅ |

## Ролі (RBAC)

| Роль | Права |
|---|---|
| `user` | перегляд власних asset і сканувань |
| `analyst` | запуск сканувань і перегляд findings |
| `admin` | керування користувачами та системою |

> Публічна реєстрація завжди створює роль `user` — поле `role` не приймається
> від клієнта. Підняття до `analyst`/`admin` робить адміністратор через
> `PATCH /api/v1/users/{id}/role`. Перший адмін створюється при старті auth з
> `ADMIN_USERNAME`/`ADMIN_PASSWORD` (`.env`).

### Модель видимості даних

Ролі різняться не тим, що можна робити, а тим, **які дані видно**. Правила
послідовні для всіх ресурсів — їх варто тримати в голові при додаванні нових:

| Ресурс | `user` | `analyst` | `admin` |
|---|---|---|---|
| **assets** | власні (`owner_id`) | власні | усі |
| **scans** | власні (`created_by`) | усі | усі |
| **findings** | власні (через `Scan.created_by`) | усі | усі |
| **reports** | власні (`created_by`) | усі | усі |

Тобто аналітик бачить усі сканування, знахідки і звіти, але **не** бачить чужих
активів — актив залишається приватним для власника. Це свідоме рішення: аналітик
має повну картину інфраструктури для аналізу, але не може витягнути дані по
чужому активу за ID.

Перевірка доступу віддає **404, а не 403** — щоб не підтверджувати існування
об'єкта для того, хто до нього не має доступу. Це видно в `assets.py`,
`scans.py` і `reports.py`.

## Структура

```text
CyberOps_PRO/
├── gateway/            # API Gateway (FastAPI): маршрутизація, JWT-гейт, заголовки identity
├── backend/            # FastAPI: core (assets/scans/findings/...) + auth (app.auth_app)
├── frontend/           # Next.js / React (App Router) UI: dashboard, assets, scans, findings, reports
├── legacy/dashboard/   # старий однофайловий дашборд на /dashboard (зворотна сумісність)
├── services/scanner/   # Nmap: build_command, run_nmap, parse_nmap_xml
├── workers/            # Celery worker (Redis broker)
├── security-lab/       # навмисно вразливі: vulnerable-api, vulnerable-web, test-db
├── monitoring/         # Prometheus, Grafana, Jaeger
├── infrastructure/     # kubernetes (kustomize) manifests, terraform (aws)
├── docs/               # architecture, deployment, demo, roadmap
├── scripts/            # demo.py (E2E демо), smoke.sh (перевірка стендів), remote-configure.sh
├── docker-compose.yml  # базовий compose (dev)
├── docker-compose.prod.yml  # prod-override: обов'язкові секрети, APP_ENV=prod, обмежені логи
├── Makefile
└── README.md
```

## Швидкий старт

**Без Docker (потрібна PostgreSQL):**

```bash
cp .env.example .env          # dev-заглушки з коробки робочі; для деплою — свої секрети
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r backend/requirements.txt
pip install -r gateway/requirements.txt
cd backend
alembic upgrade head
```

Запуск трьох процесів (окремі термінали):

```bash
uvicorn app.main:app --reload                    # core          -> :8001
uvicorn app.auth_app:app --reload --port 8002    # auth          -> :8002
cd .. && uvicorn gateway.main:app --reload --port 8000  # gateway -> :8000
```

**З Docker (API Gateway + core + auth + worker + Redis + frontend):**

```bash
docker compose up -d --build
docker compose exec core alembic upgrade head    # compose не накатує міграції сам
```

**Фронтенд без Docker (dev, окремий термінал):**

```bash
cd frontend
npm install
npm run dev              # -> http://localhost:3000
```

`NEXT_PUBLIC_API_URL` (за замовчуванням `http://localhost:8000`) задає адресу
API Gateway, яку використовує браузер.

**Перевірка:**

```bash
cd backend
python -m pytest tests -q       # тести
python -m ruff check app tests ../workers ../services ../gateway  # лінт
curl http://localhost:8000/health    # gateway /health (агрегує services)
curl http://localhost:8001/health    # core
curl http://localhost:8002/health    # auth
```

## Microservices та API Gateway (v0.7)

Застосунок розділено на два незалежні FastAPI-сервіси, перед якими стоїть
**API Gateway** (`gateway/`) — єдина публічна точка входу на порту `8000`.

| Компонент | Порт | Відповідальність |
|---|---|---|
| `gateway` | 8000 (публічний) | маршрутизація за префіксом, централізована перевірка JWT, інжекція `X-User-*` заголовків, агрегація `/health`, метрики, WebSocket-relay |
| `auth` | 8002 (внутрішній) | `/api/v1/auth*`, `/api/v1/users*`, `/api/v1/audit-logs` |
| `core` | 8001 (внутрішній) | assets, scans, findings, notifications, reports, dashboard, `/ws`, статичний дашборд `/dashboard` |
| `worker` | 9091 (метрики) | Celery + Nmap, публікує події RabbitMQ/Redis |
| `frontend` | 3000 (UI) | Next.js dashboards, звертається до Gateway з браузера |

**Маршрутизація:** префікси `/api/v1/auth`, `/api/v1/users`, `/api/v1/audit-logs`
ідуть в `auth`; решта `/api/v1/*`, `/dashboard` та `/ws` — в `core`.

**Безпека на межі (edge):**
- Публічні шляхи (login/register/refresh) проходять без токена.
- Для решти `/api/*` Gateway сам перевіряє access-токен (той самий `JWT_SECRET`).
- Gateway викидає будь-які клієнтські `X-User-*`-заголовки і підставляє
  `X-User-Id`, `X-User-Role`, `X-User-Username` з claims токена; додає
  `X-Forwarded-For` (audit-лог фіксує реальну IP клієнта).
- Сервіси незалежно перевіряють токен (defense-in-depth) та дивляться роль у БД.

**Rate limiting (v1.2):** token bucket у пам'яті процесу (`gateway/ratelimit.py`).

| Група | Ліміт | Ключ |
|---|---|---|
| `login`, `register`, `refresh`, `change-password` | 5/хв | IP |
| решта `/api/v1/*` | 120/хв | `sub` токена, а для анонімних — IP |

Відмова — `429` з `Retry-After` та `X-RateLimit-Limit`/`-Remaining`, лічильник
`gateway_rate_limited_total`. `/health` і `/metrics` не обмежені (інакше скринінг
виглядав би недоступним). Перевірка токена йде **раніше** за ліміт, щоб не
відповідати `429` на `401` — інакше ліміт можна використати як розвідник.

> Лічильник живе в пам'яті, тому при `replicas > 1` кожен под рахує свій
> ліміт (N подів = N× ліміт). У compose/K8s gateway однопроцесний; для
> горизонтального масштабування потрібен спільний бекенд (Redis) — це вже
> закладено в `redis` у стеку.

**Security headers (v1.2):** middleware додає `Strict-Transport-Security`,
`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy:
no-referrer`, `Cross-Origin-Opener-Policy`, `Permissions-Policy` і CSP.
Для API CSP максимально суворий — `default-src 'none'`. Legacy-дашборд
`/dashboard` має інлайновий `<script>`/`<style>`, тому для нього окремий,
послаблений CSP.

**TLS (v1.2):** за замовчуванням Gateway слухає HTTP — TLS термінує
балансувальник. Щоб увімкнути TLS на самому Gateway, покладіть `cert.pem`/
`key.pem` у `./certs` (каталог у `.gitignore`) і задайте:

```bash
GATEWAY_TLS_CERTFILE=/certs/cert.pem
GATEWAY_TLS_KEYFILE=/certs/key.pem
GATEWAY_TLS_VERSION=2          # ssl.TLSVersion: 2 = TLSv1.2, 3 = лише TLSv1.3
GATEWAY_TLS_CIPHERS=ECDHE+AESGCM:ECDHE+CHACHA20:ECDHE+AES256:ECDHE+AES128
```

`gateway/entrypoint.sh` перетворює їх на прапорці Uvicorn; якщо пару ключів
не задано — працюємо звичайним HTTP.

**Секрет підпису JWT:** `JWT_SECRET` має бути **не коротше 32 байт** (HMAC-SHA256),
інакше застосунок не стартує з поясненням. У `APP_ENV=production` шаблонні
значення теж відкидаються:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

**WebSocket:** `/ws` на Gateway виконує relay до `core` (`/ws?token=`), тому
дашборд продовжує працювати як раніше на `http://localhost:8000/dashboard`.

**Спільне:** сервіси використовують спільну БД та модельний шар (`backend/app`),
що спрощує розвиток; повний поділ на per-service БД — план на v0.8+.

> Swagger: core — `:8001/docs`, auth — `:8002/docs`, Gateway — `:8000/docs`
> (у gateway лише власні health/metrics; повний API див. нижче).

## Kubernetes та CI/CD (v0.8)

**Манифести** (`infrastructure/kubernetes/`, kustomize base + overlay):

```text
infrastructure/kubernetes/
├── kustomization.yaml     # root -> base
├── base/                  # namespace, config, secrets, postgres, redis, rabbitmq,
│                          # migrations Job, core, auth, gateway, worker, frontend,
│                          # prometheus, jaeger, grafana
├── overlays/dev/          # dev overlay (base + APP_ENV: dev) для kind-розгортання
└── base/grafana/          # provisioning (datasource, dashboards) як ConfigMap
```

- `core`/`auth` використовують один образ `cyberops-backend` з різними командами
  (`app.main` на 8001, `app.auth_app` на 8002); `worker` і `gateway` — окремі образи.
- `migrations` — одноразовий **Job** (`alembic upgrade head`) з `initContainer`,
  що чекає на TCP до БД (адресу бере з `DATABASE_URL`, а не хардкодить). Job
  створюється разом із усім іншим маніфестом, тобто одразу після `apply`, а
  postgres на той момент ще піднімається: без очікування Job витрачав дві з
  трьох спроб (`backoffLimit: 3`) на connection refused.
- Probes: `readiness/liveness` HTTP `/health` у всіх сервісів, **крім gateway** —
  його `/health` навмисно ходить ще й у `core`/`auth` і повертає 503, коли вони
  не готові. Для readiness це правильно, але в livenessProbe це означало, що
  kubelet перезапускав здоровий проксі через затримку внизу. Додано
  `/health/live` («процес живий», без залежностей) і перевів liveness на нього.
- Gateway — `NodePort 30080`, Grafana — `NodePort 30300`, frontend — `NodePort 30010`,
  Jaeger UI — `NodePort 30086`.
- Prometheus scrape-таргети через DNS: `gateway:8000`, `core:8001`,
  `auth:8002`, `worker:9091`, `jaeger:14269`.
- Імена змінних, які **kubelet підставляє сам** (`<SERVICE>_SERVICE_HOST`,
  `<SERVICE>_SERVICE_PORT`, `<SERVICE>_<PORTNAME>`, де для безіменного порту
  `PORTNAME = PORT`), не можуть дублювати те, що читає код. Тому порт gateway
  названо `GATEWAY_LISTEN_PORT`, а не `GATEWAY_PORT` — інакше kubectl підставляє
  в контейнер `GATEWAY_PORT=tcp://10.96.x.x:8000`, `entrypoint.sh` читає це як
  номер порту, uvicorn виходить із кодом 2, і контейнер йде в CrashLoopBackOff.
  Цей інваріант перевіряється тестом на весь клас, а не на цей один випадок.

**Конфіг і секрети (v1.12, v1.14, v1.16):** несекретні параметри (`APP_ENV`, URL
сервісів, ліміти) живуть у ConfigMap `cyberops-config`, а **усі ключі з
паролями — у Secret `cyberops-secrets`**: `POSTGRES_PASSWORD`, `JWT_SECRET`,
`DATABASE_URL` (містить пароль), `CORS_ORIGINS`, `ADMIN_USERNAME`/
`ADMIN_PASSWORD` (їх E2E бере зі Secret, щоб облікові дані не роз'їжджалися з
маніфестом) і `GRAFANA_ADMIN_PASSWORD`. ConfigMap не шифрований і читається
через `kubectl get configmap -o yaml`, тож `DATABASE_URL` у ньому — це пароль у
відкритому вигляді. Той самий інваріант стосується Grafana: `GF_SECURITY_ADMIN_PASSWORD`
мусить приходити через `secretKeyRef`, бо Service виставлений назовні
(`nodePort 30300`) — літерал у маніфесті це публічний `admin/admin`.

> **Охорона має спрацювати на обох шляхах.** `app/config.py` відмовляється
> стартувати з шаблонними `JWT_SECRET`/паролями в проді. Ключовий рядок —
> `_is_production()`: він приймає і `production`, і `prod`, бо саме `prod`
> виставляють і `docker-compose.prod.yml`, і k8s-ConfigMap. Раніше перевірка
> порівнювала з `"production"`, тож жоден реальний прод-деплой її не проходив.
> Тест, який перевіряє охорону, має використовувати те саме значення, що й
> прод-конфіги, інакше він перевіряє інший світ.
> `overlays/dev` перекриває `APP_ENV` на `dev`, бо base лишається `prod`
> для справжніх прод-оверлеїв.

Значення в `secret.yaml` — **заглушки для локального стенду**, у Git вони
не є справжніми секретами. Для продакшену підключіть зовнішній менеджер
(AWS Secrets Manager, Vault, External Secrets, Sealed Secrets) і перекрийте
значення через overlay — зокрема `CORS_ORIGINS`, де в базі стоїть лише
`http://localhost:3000`. Якщо ключ прибрати, жоден origin не буде дозволений
(це краще, ніж `"*"`).

> **Помилка, яка тут була:** `kubectl kustomize` перевіряє синтаксис, а не
> семантику, тому перенесення `DATABASE_URL` у Secret зелено пройшло CI і
> зламало Job `migrations` — він мав лише `configMapRef`, тож Alembic узяв
> дефолтний `localhost` із `app/config.py` і впав з connection refused.
> Інваріанти на цю зв'язку тепер у `tests/test_k8s_manifests.py`.

**Образи:** compass tags задаються через `IMAGE_PREFIX`/`IMAGE_TAG`
(за замовчуванням `cyberops/*:latest`):

```bash
docker compose build          # збирає cyberops/cyberops-{backend,worker,gateway,frontend}:latest
```

**CI/CD (GitHub Actions, `.github/workflows/`):**

| Воркфлоу | Коли | Що робить |
|---|---|---|
| `ci.yml` | push + PR | ruff, 239 тестів, `docker compose config -q` (база і prod-override), `kubectl kustomize`, frontend (`npm ci`, typecheck, build) |
| `ci.yml` → `security` | push + PR | Bandit (`-ll`), `pip-audit` (жорсткий gate), Trivy (поки `continue-on-error`), Semgrep `p/ci` — лише якщо задано `SEMGREP_APP_TOKEN` |
| `docker.yml` | push + tag | збірка й push 4 образів у `ghcr.io/<owner>/<repo>`: на `master` — тег `dev`, на tag `v*` — тег версії без `v` |
| `deploy.yml` | push + ручний запуск | **kind E2E**: збірка, кластер, `apply`, очікування міграцій і rollout, `scripts/smoke.sh` |
| `prod-e2e.yml` | push + ручний запуск | **compose-prod E2E**: те саме, але на тому самому `scripts/smoke.sh` |

Усі воркфлою мають `workflow_dispatch`: перший пуш у нове репо не запускає
жодного (GitHub не встигає зареєструвати файли воркфлою в тій самій гілці), а
прогін без жодного кроку не перезапускається — «cannot be retried».

`docker.yml` **не вписує** `NEXT_PUBLIC_API_URL` в опублікований образ: той,
хто візьме `ghcr.io/.../cyberops-frontend:dev`, отримає UI, який ходить у
`localhost` свого браузера. Адреса приходить у рантаймі (див. далі), тому образ
придатний для будь-якої адреси.

**Локальні перевірки те саме, що робить CI:**

```bash
cd backend
python -m pytest tests -q                 # 239 тестів
python -m ruff check app tests ../workers ../services ../gateway
python -m bandit -r app ../gateway ../workers ../services -ll   # SAST, medium+
python -m pip_audit -r requirements.txt                        # відомі CVE
```

`deploy.yml` чекає rollout **кожного** деплоймента, взятого з кластера
(`kubectl get deployments`), а не зі списку літералом у воркфлою: список у
воркфлою не оновлюється разом із маніфестами й уже розійшовся один раз
(`jaeger` не потрапив у список, тож колектор міг не піднятися, а E2E був
зелений). Крок `Diagnostics` (`if: always()`) знімає events, `describe` і логи
`current`/`--previous` для кожного пода — без нього видно лише симптом, а не
причину.

**Локальне деплоювання в kind:**

```bash
docker compose build
kind create cluster --name cyberops
kind load docker-image --name cyberops cyberops/cyberops-backend:latest cyberops/cyberops-worker:latest cyberops/cyberops-gateway:latest cyberops/cyberops-frontend:latest
kubectl apply -k infrastructure/kubernetes/overlays/dev
kubectl -n cyberops wait --for=condition=complete job/migrations --timeout=240s
kubectl -n cyberops rollout status deploy/gateway --timeout=240s
kubectl -n cyberops port-forward svc/gateway 8000:8000
```

> Ім'я кластера задавай явно: `kind load` без `--name` читає контекст `kind` і
> не знаходить нічого (`no nodes found for cluster`).
> Свої образи мають `imagePullPolicy: IfNotPresent` — для `:latest` kubelet за
> замовчуванням ставить `Always` і йде в registry за образом, якого там немає
> (`ImagePullBackOff`).

## Стенди й E2E: що саме перевіряється (v1.13–v1.16)

Проєкт має **два повноцінні стенди**, і обидва проходять **той самий** скрипт
`scripts/smoke.sh`. Копія одного тесту в двох воркфлоу розходиться з першою ж
правкою, а далі «CI зелений» нічого не означає.

| Стенд | Воркфлоу | Що піднімає |
|---|---|---|
| kind | `deploy.yml` | 11 деплойментів + Job `migrations`, порти через `kubectl port-forward` |
| compose-prod | `prod-e2e.yml` | увесь стек із `docker-compose.prod.yml` (обов'язкові секрети, `APP_ENV=prod`) |

Скрипт перевіряє поведінку, а не «процеси піднялися»:

1. **`/runtime-config.js` віддає очікувану адресу API.** Значення звіряється з
   ConfigMap/compose env, а не з константи в тесті — інакше тест підтверджував
   би себе сам. Головна перевірка проти v1.14: `NEXT_PUBLIC_*` підставляється
   під час `next build`, тож адреса, вшита в бандл, вічна.
2. **CORS так, як його робить браузер** — `OPTIONS` з `Origin` і
   `Access-Control-Request-Method`, порівняння з origin, узятим із Service.
   `curl` без `Origin` ніколи не бачив би попереднього багу.
3. **Вхід адміністратором** (облікові дані зі Secret, обмежена кількість спроб
   через backoff сида) і **створення активу з читанням назад** (201 + readback).
4. **Усі таргети Prometheus `up`** — список береться з самого Prometheus
   (`/api/v1/targets`), а при падінні в лог іде реальна причина (`lastError`).
5. **Спани прибули в Jaeger** для сервісів, через які пройшли запити вище
   (`EXPECTED_TRACE_SERVICES`), **і реально читаються** через `/api/traces` —
   сама реєстрація сервісу нічого не доводить, дані могли не дійти.
6. **Датасорс Grafana provisionований і здоровий** (`/api/datasources` +
   `/health` датасорса). `/api/health` самої Grafana тут безкоштовний: вона
   радісно віддає `ok`, навіть коли датасорс мертвий.

Якщо `TRACING_ENABLED` вимкнено, крок **падає з поясненням**, а не пропускає
перевірку мовчки — інакше стенд без спостережуваності знову був би зеленим.

У `prod-e2e.yml` адреса API свідомо **не** `localhost`, а
`http://203.0.113.10:8000` — недосяжний TEST-NET-3 (RFC 5737). Так тест
доводить головне: адреса приходить з контейнера, а не з бандлу. Якби збірка
знову почала брати її з аргументу, крок впав би тут, а не на проді.

Запустити той самий скрипт локально (після `docker compose up -d`):

```bash
GATEWAY_URL=http://localhost:8000 FRONTEND_URL=http://localhost:3000 \
EXPECTED_API_URL=http://localhost:8000 EXPECTED_ORIGIN=http://localhost:3000 \
ADMIN_USER=admin ADMIN_PASS=... \
PROMETHEUS_URL=http://localhost:9090 JAEGER_URL=http://localhost:16686 \
GRAFANA_URL=http://localhost:3001 GRAFANA_USER=admin GRAFANA_PASS=... \
EXPECTED_TRACE_SERVICES="gateway core auth" \
bash scripts/smoke.sh
```

## Terraform / Cloud (v0.9)

Модуль `infrastructure/terraform/aws/` піднімає одну EC2 (Ubuntu 22.04) з
Security Group, EIP і user-data, який ставить Docker і розгортає стек через
`docker compose up --build` прямо з Git (lift-and-shift, підходить для
демо/старту; на продуцент використати управляний Postgres і ingress).

```text
infrastructure/terraform/aws/
├── versions.tf      # terraform + providers (aws, random)
├── variables.tf     # region, key_name, admin_password, instance_type, repo_url/branch, cidr
├── main.tf          # VPC Security Group, EC2, user_data, Elastic IP
├── outputs.tf       # public_ip, ssh_command, gateway_url, frontend_url, тунель до метрик
└── user-data.sh     # cloud-init: docker.io + git clone + compose up
```

- One EC2: `t3.medium` за замовчуванням (для `--build` образів), SSH-ключ —
  існуючий key pair (`key_name`).
- SG: `22` (SSH, обов'язково явно — дефолту `0.0.0.0/0` немає), `80/443`,
  `8000` (gateway), `3000` (UI).
- `JWT_SECRET` генерується через `random_password`, пароль адміністратора
  задається змінною `admin_password` (обидва пишуться в `.env` на інстансі).
- Використання (потрібні AWS credentials):

```bash
cd infrastructure/terraform/aws
terraform init
terraform plan -var key_name=my-key -var ssh_cidr=203.0.113.10/32 \
  -var 'admin_password=...'
terraform apply -var key_name=my-key -var ssh_cidr=203.0.113.10/32 \
  -var 'admin_password=...' [-var app_public_url=https://cyberops.example.com]
```

Outputs: `public_ip`, `ssh_command`, `gateway_url`, `frontend_url`,
`observability_ssh_tunnel`. Див. наступний розділ — саме він пояснює, що
`app_public_url` такий, яким він є.

## Віддалене розгортання (v1.7)

Локально `docker compose up` працює «просто», і саме через це три речі
ламаються на справжньому сервері.

**1. Публічні порти.** У `docker-compose.yml` ззовні слухають лише
`gateway:8000` і `frontend:3000` — саме їх браузер має бачити. Усе інше
(Postgres, Redis, RabbitMQ, внутрішні `core`/`auth`, Prometheus, Jaeger,
Grafana) прив'язане до `127.0.0.1`. Метрики на EC2 доступні через
SSH-тунель (значення `observability_ssh_tunnel` в terraform outputs):

```bash
ssh -N -L 3001:localhost:3001 -L 16686:localhost:16686 -L 9090:9090 \
  -i my-key.pem ubuntu@<ip>
# Grafana :3001, Jaeger :16686, Prometheus :9090
```

Це не косметика: дефолтний compose відкривав `:5432` з `admin/admin`
seed-користувачем у публічний інтернет.

> **Конфлікт на локальній машині.** Якщо `5432` вже займає ваш власний
> PostgreSQL (або щось інше), `docker compose up` впаде на
> `ports are not available`. Задайте в `.env` `POSTGRES_PORT=5433` — це
> порт лише на хості; усередині мережі compose посилається на
> `postgres:5432`, тож `DATABASE_URL` змінювати не треба.

**2. `NEXT_PUBLIC_API_URL` вшивається в бандл під час збірки.** Зібраний
на сервері фронтенд із дефолтом `http://localhost:8000` звертатиметься до
`localhost:8000` у браузері відвідувача: UI відкривається, але порожній, і
симптом виглядає як «бекенд зламався». `docker-compose.prod.yml` робить цю
змінну обов'язковою (`${NEXT_PUBLIC_API_URL:?...}`), тож compose падає на
старті, а не мовчки.

**3. Секрети.** Базовий compose має dev-дефолти (`JWT_SECRET=dev-secret-...`,
`ADMIN_PASSWORD=admin`) — для локальної розробки це зручно, для публічного
інстансу це діра. Prod-override перетворює їх на обов'язкові:

| Змінна | Що робить prod-override |
|---|---|
| `JWT_SECRET` | обов'язкова для `core`/`auth`/`worker`/`gateway` (інакше `dev-secret-change-me...`) |
| `POSTGRES_PASSWORD` | обов'язкова для БД і `DATABASE_URL` |
| `ADMIN_PASSWORD` | обов'язкова (інакше `admin/admin` на публічній адресі) |
| `CORS_ORIGINS` | обов'язкова і має містити origin фронтенду, а не `*` |
| `NEXT_PUBLIC_API_URL` | обов'язкова, див. вище |
| `GRAFANA_ADMIN_PASSWORD` | обов'язкова |
| `APP_ENV` | `prod` замість `dev` |

Плюс `restart: unless-stopped` і `json-file` з лімітом (`10m` × `3`) на
кожен сервіс: без ліміту логи з'їдають диск t3.medium і кладуть весь стек.

**4. Міграцій у compose не було взагалі (v1.15).** `make up-prod` виконує
`docker compose up -d --build`, а міграції запускає `make migrate` — але це
`alembic` **на хості** проти `127.0.0.1:5432`. На чистій машині після
`make up-prod` таблиць не існувало: бекенд піднімається, `/health` відповідає
`ok`, сид адміна мовчки падає на відсутній таблиці — і системою не можна
скористатися. Тепер у стеку є одноразовий сервіс `migrations`
(`alembic upgrade head`, аналог k8s Job), а `core`/`auth`/`worker` чекають на
`service_completed_successfully`, а **не** на `service_started`: стенд із
падінням міграцій має зупинитися, а не піднятися й брехати `/health`. Для нього
зроблено виняток `restart: "no"` — з `unless-stopped` compose піднімав би
завершений контейнер по колу.

```bash
cp .env.example .env   # обов'язково відредагувати секрети
make up-prod           # міграції виконуються автоматично, окремим кроком не треба
make config-prod       # валідація конфігів (CI робить те саме)
```

Секрети, які лишилися шаблонними (зокрема `ADMIN_PASSWORD=admin`),
застосунок у `APP_ENV=prod` не приймає — стек підніметься з явним
помилкою, а не мовчки з admin/admin.

**Terraform + compose.** `user-data.sh` клонує репозиторій, пише в `.env`
секрети й публічну адресу, піднімає стек через prod-override і друкує
URL-и. Один нюанс: EIP доставляється **після** старту інстансу, тому на
першому boot визначення адреси може вихопити тимчасовий auto-assigned IP,
який помре разом з EIP. Тому:

- передавайте `-var app_public_url=https://cyberops.example.com` (свій
  домен) — це найкращий шлях;
- або після `terraform apply` перенаправте стек на фактичний EIP однією
  командою:

```bash
scripts/remote-configure.sh ubuntu@<eip> http://<eip>
```

Скрипт перезаписує `NEXT_PUBLIC_API_URL`/`CORS_ORIGINS`/`APP_BASE_URL` у
`.env` на інстансі і робить `compose up -d`.

## Security Lab (v1.0)

Навмисно вразливий локальний стенд для практики: `security-lab/`.

> **ВАЖЛИВО:** сервіси вразливі за задумом. Порти привʼязані тільки до
> `127.0.0.1`, стенд підключається до мережі `cyberops_default` лише для
> сканування з CyberOps. Дозволено використовувати тільки на власній машині.

```text
security-lab/
├── vulnerable-api/      # FastAPI: SQLi, command injection, IDOR, слабка авторизація, витік секретів (8100)
├── vulnerable-web/      # Flask: XSS, open redirect, path traversal, дефолтні креденшени, небезпечні cookies (8101)
├── test-db/             # PostgreSQL: слабкі креденшени lab/lab123, plaintext-паролі, картки (55432)
└── docker-compose.yml
```

**Запуск** (спершу основний стек, щоб створилася мережа `cyberops_default`):

```bash
docker compose up -d --build            # корінь проєкту
docker compose -f security-lab/docker-compose.yml up -d --build
```

**Які цілі конфігурувати в CyberOps (Dashboard → Assets):**
- `vulnerable-api` — HTTP API (81xx на локальній машині не потрібен, у
  системі скануємо за імʼям: `http://vulnerable-api:8000` або IP контейнера)
- `vulnerable-web` — `http://vulnerable-web:8001`
- `test-db` — `5432/tcp PostgreSQL` (слабкий пароль → Finding
  «Exposed PostgreSQL»)

**Практика:** Nmap з хоста (`nmap -sV -p- 127.0.0.1`), потім у Web та API:
SQLi (`/api/users?name=' OR '1'='1`), command injection (`/api/ping?host=;whoami`),
IDOR (`/api/user/1`), path traversal (`/files?name=../../etc/passwd`),
XSS (`/search?q=<script>`), open redirect (`/redirect?url=https://evil.local`).

**Скидання БД:** `docker compose -f security-lab/docker-compose.yml down -v && docker compose -f security-lab/docker-compose.yml up -d`

## AI Security Assistant (v1.0)

Для кожної знахідки (`Finding`) платформа пояснює: **що знайдено**, **чому це
проблема**, **який вплив** та **як виправити**.

```
Finding → AI Assistant → explanation + impact + risk_explanation + remediation
```

**Ендпоінт:** `POST /api/v1/findings/{id}/explain` (RBAC: власник/analyst/admin).

**Провайдери** (`backend/app/services/ai_assistant.py`):
- `AI_PROVIDER=` (порожньо) — локальні правила: шаблони за severity/service;
  працює без інтернету і покривається тестами.
- `AI_PROVIDER=ollama` — локальна LLM (Ollama, OpenAI-сумісний `/v1`):
  `AI_BASE_URL=http://localhost:11434/v1`, `AI_MODEL=llama3.2`.
- `AI_PROVIDER=openai` / `openai-compatible` — будь-який OpenAI-сумісний API:
  `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL`.

При збої LLM чи некоректній відповіді автоматично спрацьовує fallback на правила.
Відповідь містить `provider` (`rule` або `api/<model>`) для прозорості.

## Frontend (v1.0)

Next.js 14 (App Router, React 18, TypeScript, без сторонніх CSS-бібліотек —
власний темний UI), розміщений у `frontend/`.

```text
frontend/
├── src/lib/        # types (моделі API), api (fetch + токени), auth (AuthProvider), ws (useRealtime)
├── src/components/ # Nav, RequireAuth, StatCard, Pills, AIExplain
└── src/app/        # dashboard, assets, scans, scans/[id], findings, reports, notifications, settings
```

- Аутентифікація через Gateway (`/api/v1/auth/login`); токени в `localStorage`.
- Real-time події (`scan.completed`, `notification.created`) через `/ws`.
- AI Assistant: кнопка «Explain» біля кожного finding.
- Збірка: `Dockerfile` (node:20-alpine, `npm ci` → static export/next start :3000),
  сервіс у `docker-compose.yml` (порт 3000), k8s-mаніфест `base/frontend.yaml`
  (`NodePort 30010`), GHCR-image `cyberops-frontend`, job у `ci.yml`.

### Адреса API приходить у рантаймі (v1.14)

`NEXT_PUBLIC_*` підставляється під час `next build`, тож значення стає
константою в JavaScript **назавжди**. Тому образ фронтенду, зібраний без
`.env`, отримує UI, який ходить у `localhost:8000` браузера відвідувача:
інтерфейс відкривається порожнім, а симптом виглядає як «зламаний бекенд»
(те саме, що v1.7 знайшов на віддаленому compose).

- Контейнер віддає **`/runtime-config.js`** з `API_PUBLIC_URL`, а `layout.tsx`
  підвантажує його звичайним `<script>` — до гідратації, бо компоненти читають
  значення під час першого рендеру.
- Route handler має **`force-dynamic`**: без нього Next зберіг би відповідь у
  статичний бандл під час збірки, і ми б повернули рівно той самий баг. На
  build має бути `ƒ /runtime-config.js` (dynamic), а не `○`.
- Порядок джерел у `api.ts`: runtime → `NEXT_PUBLIC_API_URL` (лише для
  `npm run dev`) → `window.location.origin`. Останнє свідомо краще за
  `localhost:8000`: запит піде на поточний хост і впаде голосно (404 від Next)
  замість того, щоб піти у випадковий порт на машині відвідувача. Перевірка на
  порожність, а не `??` — Next підставляє в бандл навіть порожній рядок.
- Адреса читається **щоразу**, а не один раз на модулі: скрипт конфігу
  підвантажується під час розбору сторінки, тож на модулі значення було б ще не
  готове.
- `API_PUBLIC_URL` обов'язковий у prod-оверлеї; build-arg прибрано з compose,
  Dockerfile і `docker.yml`, тож опублікований образ не прив'язаний до адреси,
  під якою його зібрали.

## API (v0.7, через Gateway)

| Метод | Шлях | Доступ |
|---|---|---|
| POST | `/api/v1/auth/register` | public (завжди створює роль `user`) |
| POST | `/api/v1/auth/login` | public |
| POST | `/api/v1/auth/refresh` | public (refresh-токен у тілі, не в query) |
| POST | `/api/v1/auth/change-password` | authorized |
| GET | `/api/v1/auth/me` | authorized |
| GET | `/api/v1/users/me` | authorized |
| GET | `/api/v1/users` | admin |
| PATCH | `/api/v1/users/{id}` | admin |
| PATCH | `/api/v1/users/{id}/role` | admin |
| DELETE | `/api/v1/users/{id}` | admin |
| POST | `/api/v1/assets` | authorized (kind: ip/domain/hostname/docker; + агрегований ризик) |
| GET | `/api/v1/assets` | authorized (власні / admin — всі) |
| GET | `/api/v1/assets/{id}` | owner / admin |
| PATCH | `/api/v1/assets/{id}` | owner / admin |
| DELETE | `/api/v1/assets/{id}` | analyst / admin |
| POST | `/api/v1/scans` | analyst / admin (202, черга Celery) |
| GET | `/api/v1/scans` | authorized (власні / analyst — всі) |
| GET | `/api/v1/scans/{id}` | owner / analyst / admin |
| GET | `/api/v1/scans/{id}/services` | owner / analyst / admin |
| GET | `/api/v1/scans/{id}/risk` | owner / analyst / admin |
| GET | `/api/v1/scans/{id}/raw` | owner / analyst / admin; `?include_xml=false` — без самого XML |
| GET | `/api/v1/scans/{id}/raw.xml` | owner / analyst / admin (download сирого Nmap-XML) |
| GET | `/api/v1/findings` | owner (свої) / analyst / admin; фільтри `?severity=&scan_id=` |
| POST | `/api/v1/findings/{id}/explain` | owner / analyst / admin (AI Assistant) |
| POST | `/api/v1/reports` | analyst / admin (201; `report_type=asset\|scan`) |
| GET | `/api/v1/reports` | owner (свої) / analyst / admin; фільтр `?report_type=` |
| GET | `/api/v1/reports/{id}` | owner / analyst / admin |
| GET | `/api/v1/notifications` | authorized (власні); `?unread_only=`, `?channel=web\|email\|telegram` |
| GET | `/api/v1/notifications/preferences` | authorized |
| PATCH | `/api/v1/notifications/preferences` | authorized |
| POST | `/api/v1/notifications/test` | authorized; `{channel}` → 202 |
| POST | `/api/v1/notifications/{id}/retry` | authorized (власні, email/telegram) |
| GET | `/api/v1/notifications/{id}` | authorized (власні) |
| PATCH | `/api/v1/notifications/{id}/read` | authorized (власні) |
| POST | `/api/v1/notifications/read-all` | authorized |
| GET | `/api/v1/audit-logs` | admin; фільтри `?user_id=&method=&path=` |
| GET | `/api/v1/dashboard` | authorized (своя статистика) |
| GET | `/metrics` | public (Prometheus) |
| GET | `/health` | public |

Swagger: `http://localhost:8000/docs`

**WebSocket:** `ws://localhost:8000/ws?token=<access_token>` — real-time події
(`scan.completed`, `notification.created`) для поточного користувача.

**Dashboard:** `http://localhost:3000` — фронтенд Next.js (`frontend/`):
підключення до `/ws`, статистика `/api/v1/dashboard`.

> Старий однофайловий дашборд: `http://localhost:8000/dashboard/`
> (`legacy/dashboard/index.html`) — лишається для зворотної сумісності.
> Раніше бекенд монтував на `/dashboard` увесь каталог `frontend/`, а gateway
> не вимагає токен для цього шляху — тож публічно віддавалися `node_modules/`,
> `.env.example` і `.next/`. Тепер монтується тільки `legacy/dashboard/`.

### Сканування (етика)

- Дозволені лише **приватні/loopback-адреси**; публічні блокуються,
  доки `SCAN_ALLOW_PUBLIC=false` (за замовчуванням).
- Сканування виконує `worker` (Celery + Nmap) поза API-процесом;
  статуси: `pending → running → done | failed`.
- **Завислі скан не живуть вічно** (v1.4):
  - якщо черга недоступна, API одразу переводить щойно створений скан у
    `failed` і відповідає `503` — раніше рядок лишався `pending` назавжди;
  - `worker` запускається з `-B` (celery beat) і раз на
    `SCAN_REAPER_INTERVAL_SECONDS` запускає `workers.tasks.reap_stale_scans`,
    який переводить у `failed` скан, що не дійшов до `finished_at` за
    `SCAN_STALE_AFTER_SECONDS` (за замовчуванням 900с). Це покриває падіння
    воркера, OOM-рестарт контейнера та повідомлення, що загубилося в брокері;
  - `SCAN_STALE_AFTER_SECONDS` має бути **більший** за `NMAP_TIMEOUT_SECONDS`,
    інакше beat вб'є ще живий скан.

### Сирий Nmap-архів (v1.5)

Після сканування worker зберігає **повний XML від nmap** — це первинний доказ
того, що саме бачила ціль. Архів стискається gzip-ом (`scans.raw_xml_gz`,
міграція `0007_scan_raw_archive`) і доступний двома способами:

| Запит | Що віддає |
|---|---|
| `GET /api/v1/scans/{id}/raw` | метадані (розмір, SHA-256, версія nmap, число хостів) + розпарсений «deep»-результат; сам XML — лише якщо вміщується в `SCAN_RAW_XML_MAX_CHARS` (за замовчуванням 400k), інакше `truncated: true` |
| `GET /api/v1/scans/{id}/raw.xml` | файл `nmap-<host>-<id>.xml` (`Content-Disposition: attachment`) для офлайн-аналізу |

- `GET /api/v1/scans/{id}` **більше не віддає** сирий XML: для `-sV` з NSE це
  сотні кілобайт на кожне відкриття сторінки. Крім того, ендпоинти, які не
  показують архів, відкладають (`defer`) завантаження колонки.
- Що з'явилося в розпарсеному `result` (те, що парсер раніше викидав):
  версія та аргументи nmap, `scaninfo`, **усі** hostname'и, OS-відпечатки з
  точністю, NSE-вивід скриптів (хостів і портів, обрізаний до 4000 символів),
  `uptime`/`distance`, `runstats` (elapsed, hosts up/down/total).
- Старі рядки, записані до міграції, лежать у plain-колонці `raw_xml` — читання
  їх працює, нових записів туди немає.
- UI: панель «Сирий Nmap-архів» на `scans/[id]` — метадані, картки хостів з
  OS/скриптами, кнопки «Завантажити .xml» та «Показати сирий XML» (XML
  вантажиться лише за кліком, бо на /24 це мегабайти).

### Services, Findings, Risk Score

- Після успішного сканування worker зберігає знайдені **відкриті порти як
  `services`** (порт, protocol, service, product, version, CPE).
- Зі служб виводяться **`findings`** за базою правил (telnet, rlogin, VNC,
  Redis/MongoDB без автентифікації, MSSQL, SMB тощо) з серйозністю
  `info | low | medium | high | critical` та рекомендаціями.
- **Risk Score** (0–100) сумує ваги знахідок; рівень:
  `<20 LOW`, `<45 MEDIUM`, `<75 HIGH`, інакше `CRITICAL`.
  Зберігається у скануванні та відданий через `/scans/{id}/risk`.

### Ризик активу (v1.6)

У відповідях `/api/v1/assets` (і `{id}`, `POST`, `PATCH`) з'явилися поля
агрегованого ризику — рахуються з `scans` активу, окремої колонки в таблиці
активів немає:

| Поле | Що означає |
|---|---|
| `risk_score` / `risk_level` | **поточний** стан: останнє завершене сканування |
| `max_risk_score` / `max_risk_level` | найгірший ризик за всю історію (щоб не забути, коли актив був уразливий) |
| `scans_count` | кількість усіх спроб, включно з `failed` |
| `last_scan_at` | час останньої спроби (`finished_at`), тож видно й невдалі |

- `null` у `risk_score` = ще не було жодного завершеного сканування (UI показує
  «не скановано»); рівні рахуються тим самим `risk_level_from_score`, що й для
  сканування, тож бейджі не плутаються між собою.
- Сканування враховуються **всі**, а не лише власні: чужий актив недоступний
  для сканування, а аналітик з іншої команди бачить його так само, як власник.
- `POST`/`PATCH` теж повертають ці поля — інакше бейдж зникав би до
  перезавантаження сторінки.
- UI: колонки «Ризик», «Історія» (макс + останній скан), «Скани» та
  сортування за ризиком; непросканований актив іде в кінець.

### Notifications, Reports, Audit Logs, Events (v0.4)

- **Notifications** — worker створює сповіщення власнику сканування після
  завершення та при знахідках високої/критичної важливості.
  Читаються через `/notifications`; `is_read` керується PATCH/read-all.
- **Reports** — аналітик/адмін формує звіт по цілі або скану
  (`/reports`), зберігається JSON з summary, services і findings.
- **Audit Logs** — middleware записує кожен `/api` запит (користувач, метод,
  шлях, статус, IP, UA); перегляд тільки admin (`/audit-logs`).
- **RabbitMQ events** — воркер публікує `scan.completed` і `finding.raised`,
  API — `report.generated` (topic `cyberops.events`). Публікація тиха:
  недоступність брокера не ламає API.
- RabbitMQ піднімається `docker compose` разом із postgres/redis.

### Канали сповіщень: Email, Telegram (v1.1)

Кожне сповіщення має поле `channel` (`web` / `email` / `telegram`) і `status`
(`sent` / `pending` / `failed` / `skipped`) — видно в UI на сторінці
Notifications разом із фільтром по каналу та кнопкою «Повторити» для
невдалих листів.

**Як це працює.** Worker створює рядок `web` завжди. Якщо severity ≥ поріг,
додатково створюються рядки `email`/`telegram` зі статусом `pending`, а їх
доставляє окремий Celery-таск `workers.tasks.deliver_notification` — SMTP чи
Telegram API не блокують ані сканування, ані API. Помилки доставки пишуться в
`notifications.error`, лічильник — `notifications_delivered_total`.

**Поріг важливості.** `NOTIFY_MIN_SEVERITY` — серверна підлога: користувач може
зробити поріг суворішим, але не може послабити політику сервера. Дієвий поріг
повертається в `effective_min_severity`.

**Налаштування.** UI: Settings → «Канали сповіщень» (`email`, `telegram_chat_id`,
перемикачі, мінімальний рівень, кнопки «Тест Email»/«Тест Telegram»).
API: `GET`/`PATCH /api/v1/notifications/preferences`, `POST /api/v1/notifications/test`.

**Зовнішні змінні** (усі вимкнені за замовчуванням):

| Змінна | Призначення |
|---|---|
| `NOTIFICATIONS_ENABLED` | аварійний вимикач усіх зовнішніх каналів |
| `NOTIFY_MIN_SEVERITY` | серверний поріг (`info`…`critical`) |
| `APP_BASE_URL` | базовий URL фронтенду для посилань у листах/повідомленнях |
| `SMTP_ENABLED`, `SMTP_HOST`, `SMTP_PORT` | вмикач та адреса SMTP-сервера |
| `SMTP_USER`, `SMTP_PASSWORD` | автентифікація (порожньо = без логіну) |
| `SMTP_FROM`, `SMTP_FROM_NAME` | відправник |
| `SMTP_STARTTLS`, `SMTP_SSL`, `SMTP_TIMEOUT_SECONDS` | TLS-режим і таймаут |
| `TELEGRAM_ENABLED`, `TELEGRAM_BOT_TOKEN` | вмикач і токен від @BotFather |
| `TELEGRAM_CHAT_ID` | чат за замовчуванням, якщо користувач не задав свій |
| `TELEGRAM_API_BASE` | база Telegram API (для локального mock) |

**Локальний стенд для email** — без зовнішніх серверів:

```bash
# у .env:
#   SMTP_ENABLED=true
#   SMTP_HOST=mailpit
#   SMTP_PORT=1025
#   SMTP_STARTTLS=false
docker compose --profile mail up -d
# пошта: http://localhost:8025
```

**Telegram**: токен від [@BotFather](https://t.me/BotFather), далі напишіть
боту і дізнайтеся `chat_id` через
`curl https://api.telegram.org/bot<TOKEN>/getUpdates`. Повідомлення
надсилаються в HTML з екрануванням вводу й обрізанням до ліміту Telegram.

### Realtime, WebSocket, Dashboard (v0.5)

- **WebSocket `/ws?token=`** — за авторизованим з'єднанням надсилаються події
  `scan.completed` і `notification.created` саме власнику сканування.
- **Транспорт** — `REALTIME_MODE`:
  - `memory` (dev/тести) — події в межах процесу;
  - `redis` (compose) — воркер публікує через Redis pub/sub, API доставляє на WebSocket.
- **Dashboard** — статична сторінка `legacy/dashboard/index.html` на `/dashboard/`:
  WebSocket + REST `/api/v1/dashboard` (unread, assets, high-risk, останні скани).
- **E2E-тести** — WebSocket через `TestClient` (`/ws`, відхилення недійсного токена,
  доставка тільки власнику), статичний дашборд, статистика з урахуванням ролей.

### Observability (v0.6)

- **Prometheus** — scrape-таргетів тепер чотири: `gateway:8000` (метрики
  gateway: `gateway_requests_total`, `gateway_ws_connections_total`),
  `core:8001` і `auth:8002` (`http_requests_total`, `scan_*` — на core),
  `worker:9091` (скан-процеси). `/metrics` віддає: `http_requests_total`
  (method, path-бакет, status), `scan_duration_seconds` (histogram),
  `scan_results_total` (status, risk_level), `scan_services_total`.
- **Grafana** — профільно provisioned дашборд `monitoring/grafana/provisioning`
  (джерело Prometheus + панелі трафіку, тривалості скан-запусків, ризиків);
  `http://localhost:3001` (admin/admin локально; у prod-оверлеї
  `GRAFANA_ADMIN_PASSWORD` обов'язковий, а в k8s пароль приходить із Secret).
- **Structured logs** — `LOG_JSON=true` перемикає логери на JSON-формат
  (`ts, level, logger, message` + додаткові поля).
- **OpenTelemetry → Jaeger** (v1.2) — `TRACING_ENABLED=true` + `OTLP_ENDPOINT`
  підключає OTLP/HTTP-експортер; у compose Jaeger вже у стеку, тому
  `OTLP_ENDPOINT` перекривається на `http://jaeger:4318/v1/traces`.
  UI — `http://localhost:16686`, у k8s — `NodePort 30086`.
   | Сервіс | `TRACING_SERVICE_NAME` | Що видно у Jaeger |
   |---|---|---|
   | `gateway` | `gateway` | кожен запит + **клієнтський спан на виклик до core/auth** |
   | `core` | `core` | автотрейс HTTP-запитів + `scan.run` з worker-ів |
   | `auth` | `auth` | login/register/refresh |
   | `worker` | `worker` | `scan.run` (scan.id, host, type, outcome, risk) |

   Джерело даних Jaeger provisioning'у додано в Grafana, Prometheus скрейпить
   внутрішні метрики Jaeger (`jaeger:14269`).

   Деталі реалізації, які варто знати:
   - `TracerProvider` створюється з `Resource`, де `service.name` береться з
     `TRACING_SERVICE_NAME` — без нього Jaeger згрупував би всі сервіси в один
     `unknown_service`;
   - **gateway в інструментований окремо (v1.3)**: раніше траса починалася
     одразу в `core`/`auth`, тож першого хопу не було видно взагалі. Тепер у
     Jaeger видно ланцюг `gateway (server) → httpx GET (client) → core (server)`,
     а `traceparent` прокидається вгору — це одна траса на весь запит, і в ній
     видно, скільки часу gateway чекав на бекенд;
   - gateway лежить в окремому образі (`gateway/Dockerfile` копіює лише
     `gateway/`), тому `gateway/tracing.py` — свідомий дубль
     `app/services/tracing.py`; єдиниця відмінність — додаткова інструментація
     httpx. Коли з'явиться спільний пакет, варто злити;
   - `/metrics` і `/health` виключені з трасування (`excluded_urls`): Prometheus
     скрейпить їх кожні 15с, тобто без виключення це ~5.7 тис. сміттєвих спанів
     на добу на кожен сервіс;
   - ініціалізація ідемпотентна: OTel забороняє перевизначати глобальний
     провайдер, тому повторний виклик просто повертає вже створений;
   - `get_tracer()` бере трасер із нашого провайдера, а не з глобального — інакше
     перша ж ініціалізація лишила б глобальний no-op, і ручні спани воркера
     зникли б;
   - воркер викликає `init_tracing()` при імпорті (у Celery немає FastAPI-апу,
     але `scan.run` створюється вручну);
   - інструментація httpx глобальна й лишається на весь процес — у production
     `setup_tracing()` викликається один раз при старті, у тестах це враховано
     в `tests/test_gateway_tracing.py`;
   - якщо колектор недоступний, `BatchSpanProcessor` лише пише помилки в лог —
     застосунок працює далі.

### Моніторинг, який працює (v1.16)

До v1.16 весь цей стек був увімкнений «на очі»: Jaeger, Prometheus і Grafana
піднімалися на обох стендах, а OTLP-трасування було увімкнено скрізь ще з
v1.3 — але **ні одна перевірка не дивилася, чи вони бачать те, що їм доручено**.

- **Кожен таргет скрейпу мусить мати Service, який експортує саме цей порт.**
  Регресія: Prometheus скрейпив `jaeger:14269` (правильний admin-порт Jaeger
  all-in-one), але k8s-Service `jaeger` експортував лише `4318` і `16686`.
  Prometheus ходить на Service-адресу, а не на Pod IP, тож неоголошений порт
  недоступний і таргет був `DOWN` завжди. Це невидимий симптом: `kustomize`
  такий конфіг приймає, compose так само, а в Grafana це виглядає як порожня
  панель — «немає трафіку».
- **Дві копії конфігу Prometheus** (`monitoring/prometheus.yml`, який монтує
  compose, і копія в k8s-ConfigMap) — два незалежні джерела правди. Kustomize
  не дозволяє посилатися на файл поза своїм каталогом, тому єдиним джерелом
  лишається файл, а тест перевіряє збіжність копії з ним.
- **Пароль Grafana в k8s приходить із Secret** (`GF_SECURITY_ADMIN_PASSWORD` +
  `GF_SECURITY_ADMIN_USER` через `secretKeyRef`), а не літералом у маніфесті.
  Service виставлений назовні (`nodePort 30300`), тож літерал `admin` — це
  публічний вхід, поки compose-prod вимагав обов'язковий `GRAFANA_ADMIN_PASSWORD`.
  Це та сама форма, що `APP_ENV="production"` проти реального `"prod"`: захист
  був в одному шляху й мертвий у іншому.
- **E2E перевіряє результат, а не наявність**: таргети `up`, спани прибули в
  Jaeger і читаються, датасорс Grafana здоровий (див. «Стенди й E2E»).
- **Трасування не ламається від того, *коли* його ввімкнули.** Сама ця
  перевірка знайшла четвертий баг: у Jaeger був лише `gateway`, а `core` і
  `auth` не відправляли нічого. `setup_tracing(app)` викликався з `lifespan`,
  але стек middleware до того вже побудовано, а `instrument_app()` лише
  підміняє `build_middleware_stack` і сам її не викликає — тож middleware OTel
  у ланцюг не потрапляв. Без жодного винятку: сервіс працював, а спани не
  йшли. `gateway` маскував це, бо інструментується не через FastAPI. Тепер
  `setup_tracing` перебудовує стек, якщо він уже є, тож не залежить від того,
  з якого місця його викликали.

> Спостерігаємість — не «увімкнено», а «бачить». Різниця між ними коштувала
> чотири версії: кожна з них знайшла шар, який виглядав працездатним, бо
> ніхто не перевіряв результат.
## Знайдені помилки (v1.7–v1.16)

Серія багів, знайдених на живих стендах, коли CI був зелений. Спільна форма
всіх: **опис правильний, перевірка синтаксична** — `ruff`, `kustomize`,
`docker compose config -q`, `kubectl apply` не доводять, що система працює.

| Симптом | Причина | Чому не помітив CI | Версія |
|---|---|---|---|
| `ImagePullBackOff` (frontend) | образ без тегу = `:latest` → `imagePullPolicy: Always` → kubelet йде в registry за образом, якого там немає | `kustomize` не валідує pull-policy; решта деплойментів мали `IfNotPresent` явно | v1.13 |
| `CrashLoopBackOff` (gateway) | kubelet підставляє в контейнер змінні кожного Service: `<SVC>_<PORTNAME>`, де для безіменного порту `PORTNAME = PORT`. Тобто `GATEWAY_PORT=tcp://10.96.x.x:8000` — рівно те ім'я, яке читав `entrypoint.sh`; uvicorn виходив із кодом 2 | змінної `GATEWAY_PORT` **немає в жодному маніфесті** — у YAML, у kustomize і в diff'і її не видно, вона з'являється лише на живому кластері | v1.13 |
| `migrations`: дві спроби з трьох витрачено | Job створюється одразу після `apply`, а postgres ще піднімається; Alembic падав на connection refused | `kubectl apply` не чекає на залежності; на повільнішому CI четвертої спроби не було б — пайплайн зупинився б на таймауті | v1.13 |
| gateway рестартувався здоровим | `livenessProbe` стояв на агрегованому `/health`, який ходить у `core`/`auth` і повертає 503, коли вони не готові | жоден тест не знав, що `/health` залежить від нижніх сервісів; поки тривали міграції, це гарантований цикл рестартів | v1.13 |
| Воркфлою не парсилися (перший пуш) | `secrets` у кроковому `if` (контекст недоступний на цьому рівні), `lower()` не існує в мові виразів GH Actions, `setup-trivy@v0.2.3` не існує, `kind load` без `--name` шукає інший кластер | прогін без жодного кроку не перезапускається («cannot be retried») — помилку довелося дістати через `workflow_dispatch` | v1.13 |
| `kubectl apply` відхиляв маніфест | `nodePort` без `type: NodePort` у `jaeger.yaml`; ключі ConfigMap `datasources/datasource.yaml` зі `/` (regex `[-._a-zA-Z0-9]+`) | kustomize таке дозволяє; відхиляється весь apply, тож однією помилкою зупинялося все розгортання | v1.13 |
| `migrations` Job: `ValidationError` замість Alembic | `JWT_SECRET: change-me-in-production-now` у k8s `secret.yaml` — 27 байт, HS256 вимагає ≥ 32; валідатор з v1.2 падав ще до `alembic upgrade` | Job ніхто не запускав — CI перевіряв лише `kustomize` | v1.13 |
| Охорона шаблонних секретів була **мертвою** | перевірка порівнювала `app_env == "production"`, а і compose-prod, і k8s-ConfigMap виставляють `APP_ENV: prod`. Тобто жоден реальний прод не проходив ані JWT, ані `admin/admin` | тести користувалися рядком `"production"` — перевіряли не те значення, що в прод-конфігах | v1.13 |
| UI в k8s відкривався порожнім | `NEXT_PUBLIC_API_URL` вписується в бандл під час `next build`; образ збирався без `.env` | старий E2E робив один `curl /health` | v1.14 |
| Кожен запит браузера блокувався CORS | у k8s UI живе на NodePort `30010`, а `CORS_ORIGINS` містив лише `http://localhost:3000` | `curl` не надсилає `Origin` — попередній E2E цього бачити не міг | v1.14 |
| Адміністратора **не існувало** | pod `auth` піднімається одночасно з міграціями, тож таблиці `users` ще немає; сид падав із `ConnectionRefusedError`, помилку ковтали, а в коментарі було «наступний рестарт добере решту» — рестарту не планувалося | усі поді `Running`, `/health` зелений, а увійти неможливо; `admin_seed_failed` губиться серед помилок старту | v1.14 |
| `KeyError` у лозі сида | `extra={"created": ...}` — зарезервоване поле `LogRecord`; `logging` піднімає на ньому `KeyError`, тобто впав би увесь сид, а не просто не залогувався | знайдено при написанні тестів на сид | v1.14 |
| compose-prod не мав міграцій | `make up-prod` їх не виконує, а `make migrate` — це `alembic` на хості; на чистій машині таблиць немає, `/health` каже `ok`, сид мовчки падає | стенд проходив лише `docker compose config -q` | v1.15 |
| Опублікований образ прив'язаний до адреси збірки | `docker.yml` збирав frontend із `build-args: NEXT_PUBLIC_API_URL=http://localhost:8000` і публікував у GHCR | кожен, хто візь `cyberops-frontend:dev`, отримує UI, який ходить у `localhost` свого браузера | v1.15 |
| Таргет Prometheus `jaeger:14269` завжди `DOWN` | Service `jaeger` експортував лише `4318` і `16686`; Prometheus ходить на Service-адресу, тож неоголошений порт недоступний | `kustomize`/compose приймають; статус таргетів не читав ніхто, у Grafana це порожня панель | v1.16 |
| `jaeger` поза rollout-циклом E2E | цикл `for d in ...` у `deploy.yml` містив 10 імен, а в base їх 11 | колектор міг не піднятися, а E2E був зелений: усі сервіси надсилали OTLP-спани в те, чого нема | v1.16 |
| k8s-Grafana з `admin/admin` | `GF_SECURITY_ADMIN_PASSWORD: admin` літералом у `grafana.yaml`, при тому що compose-prod вимагав обов'язковий пароль; Service на `nodePort 30300` | охорона була лише в compose-шляху й мертва в k8s-шляху | v1.16 |
| `core` і `auth` не відправляли в Jaeger **жодного** спана | `setup_tracing(app)` викликався з `lifespan`, але Starlette будує стек middleware на першому ASGI-виклику, тобто раніше, а `instrument_app()` лише підміняє `build_middleware_stack` і сам її не викликає | жодного винятку, сервіс здоровий і `/health` зелений; наявні тести трасування інструментували **свіжий** app до першого запиту — інший порядок, ніж у проді; `gateway` працював, бо інструментується не через FastAPI, і маскував пустоту | v1.16 |

### Чому всі ці баги проіснули

- **Статична перевірка ≠ перевірка семантики.** `kubectl kustomize` і
  `docker compose config` доводять, що YAML валідний; pull-policy, реальні
  порти Service, порядок залежностей і значення змінних для кубера живуть в
  іншому шарі.
- **Тест, який підтверджує себе сам, гірший за відсутність тесту.** Очікувані
  значення в E2E беруться з розгорнутого кластера/ConfigMap/Secret, а не з
  константи в самому тесті, інакше він зелений рівно тоді, коли змінна не
  доїде.
- **«Процеси піднялися» і «системою можна скористатися» — різні твердження.**
  Старий smoke-тест був зелений тричі поспіль на стенді, у якому ніхто не
  міг увійти.
- **Діагностика — перший крок, а не останній.** Логи живуть у кластері, а не в
  лозі запуску; без кроку `Diagnostics` наступна сесія вгадує причину. Так
  знайшли колізію `GATEWAY_PORT` — перша, хибна версія причини
  (`livenessProbe`) була перевірена й не підтвердилася.
- **Один скрипт на два стенди.** Копія smoke-тесту в двох воркфлоу розходиться
  з першою ж правкою, а далі «CI зелений» перестає щось означати.

> Інваріанти на весь клас багів живуть у `backend/tests/test_k8s_manifests.py`
> (колізії імен із Service, порти таргетів, залежності `envFrom`/`secretRef`,
> семантика, яку не ловить kustomize) і `test_compose_exposure.py` (що світиться
> назовні, обов'язковість секретів, порядок запуску compose-prod). Кожен
> перевірено у реверсі — на відкачених правках відповідні тести падають.

Детальний хронологічний розбір кожної версії — у `docs/roadmap.md`.

