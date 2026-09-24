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
| **1.0** | 🔄 | Security Lab ✅, AI Assistant ✅, документація, demo |

## Ролі (RBAC)

| Роль | Права |
|---|---|
| `user` | перегляд власних asset і сканувань |
| `analyst` | запуск сканувань і перегляд findings |
| `admin` | керування користувачами та системою |

## Структура

```text
CyberOps_PRO/
├── gateway/            # API Gateway (FastAPI): маршрутизація, JWT-гейт, заголовки identity
├── backend/            # FastAPI: core (assets/scans/findings/...) + auth (app.auth_app)
├── frontend/           # Next.js / React (з 0.3+)
├── services/scanner/   # Nmap: build_command, run_nmap, parse_nmap_xml
├── workers/            # Celery worker (Redis broker)
├── security-lab/       # навмисно вразливі: vulnerable-api, vulnerable-web, test-db
├── monitoring/         # Prometheus, Grafana, Jaeger
├── infrastructure/     # kubernetes (kustomize) manifests, terraform (aws)
├── docs/
├── scripts/
├── docker-compose.yml
├── Makefile
└── README.md
```

## Швидкий старт

**Без Docker (потрібна PostgreSQL):**

```bash
cp .env.example .env
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

**З Docker (API Gateway + core + auth + worker + Redis):**

```bash
docker compose up -d --build
```

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

**Маршрутизація:** префікси `/api/v1/auth`, `/api/v1/users`, `/api/v1/audit-logs`
ідуть в `auth`; решта `/api/v1/*`, `/dashboard` та `/ws` — в `core`.

**Безпека на межі (edge):**
- Публічні шляхи (login/register/refresh) проходять без токена.
- Для решти `/api/*` Gateway сам перевіряє access-токен (той самий `JWT_SECRET`).
- Gateway викидає будь-які клієнтські `X-User-*`-заголовки і підставляє
  `X-User-Id`, `X-User-Role`, `X-User-Username` з claims токена; додає
  `X-Forwarded-For` (audit-лог фіксує реальну IP клієнта).
- Сервіси незалежно перевіряють токен (defense-in-depth) та дивляться роль у БД.

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
│                          # migrations Job, core, auth, gateway, worker, prometheus, grafana
├── overlays/dev/          # dev overlay (= base, для kind-розгортання)
└── base/grafana/          # provisioning (datasource, dashboards) як ConfigMap
```

- `core`/`auth` використовують один образ `cyberops-backend` з різними командами
  (`app.main` на 8001, `app.auth_app` на 8002); `worker` і `gateway` — окремі образи.
- `migrations` — одноразовий **Job** (`alembic upgrade head`).
- Probes: `readiness/liveness` HTTP `/health` у всіх сервісів.
- Gateway — `NodePort 30080`, Grafana — `NodePort 30300`.
- Prometheus scrape-таргети через DNS: `gateway:8000`, `core:8001`,
  `auth:8002`, `worker:9091`.

**Образи:** compass tags задаються через `IMAGE_PREFIX`/`IMAGE_TAG`
(за замовчуванням `cyberops/*:latest`):

```bash
docker compose build          # збирає cyberops/cyberops-{backend,worker,gateway}:latest
```

**CI/CD (GitHub Actions, `.github/workflows/`):**
- `ci.yml` — тести + ruff + `docker compose config -q` + `kubectl kustomize` валідація.
- `docker.yml` — збірка та push образів до `ghcr.io/<owner>/<repo>`:
  on push до `master` — тег `dev`, on tag `v*` — тег версії без `v`.
- `deploy.yml` — **kind E2E**: збирає образи, створює kind-кластер, застосовує
  overlay, чекає migrations Job і rollout, тест `/health` через порт-форвард gateway:8000.

**Локальне деплоювання в kind:**

```bash
docker compose build
kind create cluster
kind load docker-image cyberops/cyberops-backend:latest cyberops/cyberops-worker:latest cyberops/cyberops-gateway:latest
kubectl apply -k infrastructure/kubernetes/overlays/dev
kubectl -n cyberops wait --for=condition=complete job/migrations --timeout=240s
kubectl -n cyberops rollout status deploy/gateway --timeout=240s
kubectl -n cyberops port-forward svc/gateway 8000:8000
```

## Terraform / Cloud (v0.9)

Модуль `infrastructure/terraform/aws/` піднімає одну EC2 (Ubuntu 22.04) з
Security Group, EIP і user-data, який ставить Docker і розгортає стек через
`docker compose up --build` прямо з Git (lift-and-shift, підходить для
демо/старту; на продуцент використати управляний Postgres і ingress).

```text
infrastructure/terraform/aws/
├── versions.tf      # terraform + providers (aws, random)
├── variables.tf     # region, key_name, instance_type, repo_url/branch, cidr
├── main.tf          # VPC Security Group, EC2, user_data, Elastic IP
├── outputs.tf       # public_ip, ssh_command, gateway_url
└── user-data.sh     # cloud-init: docker.io + git clone + compose up
```

- One EC2: `t3.medium` за замовчуванням (для `--build` образів), SSH-ключ —
  існуючий key pair (`key_name`).
- SG: `22` (SSH), `80/443`, `8000` (gateway).
- `JWT_SECRET` генерується через `random_password` і вписується в `.env`.
- Використання (потрібні AWS credentials):

```bash
cd infrastructure/terraform/aws
terraform init
terraform plan -var key_name=my-key
terraform apply -var key_name=my-key
```

Outputs: `public_ip`, `ssh_command`, `gateway_url` (gateway:8000).

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

## API (v0.7, через Gateway)

| Метод | Шлях | Доступ |
|---|---|---|
| POST | `/api/v1/auth/register` | public |
| POST | `/api/v1/auth/login` | public |
| POST | `/api/v1/auth/refresh` | public |
| POST | `/api/v1/auth/change-password` | authorized |
| GET | `/api/v1/auth/me` | authorized |
| GET | `/api/v1/users/me` | authorized |
| GET | `/api/v1/users` | admin |
| PATCH | `/api/v1/users/{id}` | admin |
| PATCH | `/api/v1/users/{id}/role` | admin |
| DELETE | `/api/v1/users/{id}` | admin |
| POST | `/api/v1/assets` | authorized (kind: ip/domain/hostname/docker) |
| GET | `/api/v1/assets` | authorized (власні / admin — всі) |
| GET | `/api/v1/assets/{id}` | owner / admin |
| PATCH | `/api/v1/assets/{id}` | owner / admin |
| DELETE | `/api/v1/assets/{id}` | analyst / admin |
| POST | `/api/v1/scans` | analyst / admin (202, черга Celery) |
| GET | `/api/v1/scans` | authorized (власні / analyst — всі) |
| GET | `/api/v1/scans/{id}` | owner / analyst / admin |
| GET | `/api/v1/scans/{id}/services` | owner / analyst / admin |
| GET | `/api/v1/scans/{id}/risk` | owner / analyst / admin |
| GET | `/api/v1/findings` | owner (свої) / analyst / admin; фільтри `?severity=&scan_id=` |
| POST | `/api/v1/findings/{id}/explain` | owner / analyst / admin (AI Assistant) |
| POST | `/api/v1/reports` | analyst / admin (201; `report_type=asset\|scan`) |
| GET | `/api/v1/reports` | owner (свої) / analyst / admin; фільтр `?report_type=` |
| GET | `/api/v1/reports/{id}` | owner / analyst / admin |
| GET | `/api/v1/notifications` | authorized (власні); `?unread_only=` |
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

**Dashboard:** `http://localhost:8000/dashboard/` — статичний real-time дашборд:
підключення до `/ws`, оновлення статистики `/api/v1/dashboard`.

### Сканування (етика)

- Дозволені лише **приватні/loopback-адреси**; публічні блокуються,
  доки `SCAN_ALLOW_PUBLIC=false` (за замовчуванням).
- Сканування виконує `worker` (Celery + Nmap) поза API-процесом;
  статуси: `pending → running → done | failed`.

### Services, Findings, Risk Score

- Після успішного сканування worker зберігає знайдені **відкриті порти як
  `services`** (порт, protocol, service, product, version, CPE).
- Зі служб виводяться **`findings`** за базою правил (telnet, rlogin, VNC,
  Redis/MongoDB без автентифікації, MSSQL, SMB тощо) з серйозністю
  `info | low | medium | high | critical` та рекомендаціями.
- **Risk Score** (0–100) сумує ваги знахідок; рівень:
  `<20 LOW`, `<45 MEDIUM`, `<75 HIGH`, інакше `CRITICAL`.
  Зберігається у скануванні та відданий через `/scans/{id}/risk`.

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

### Realtime, WebSocket, Dashboard (v0.5)

- **WebSocket `/ws?token=`** — за авторизованим з'єднанням надсилаються події
  `scan.completed` і `notification.created` саме власнику сканування.
- **Транспорт** — `REALTIME_MODE`:
  - `memory` (dev/тести) — події в межах процесу;
  - `redis` (compose) — воркер публікує через Redis pub/sub, API доставляє на WebSocket.
- **Dashboard** — статична сторінка `frontend/index.html` на `/dashboard/`:
  WebSocket + REST `/api/v1/dashboard` (unread, assets, high-risk, останні скани).
- **E2E-тести** — WebSocket через `TestClient` (`/ws`, відхилення недійсного токена,
  доставка тільки власнику), статичний дашборд, статистика з урахуванням ролей.

### Observability (v0.6)

- **Prometheus** — scrape-таргетів тепер чотири: `gateway:8000` (метрики
  gateway: `gateway_requests_total`, `gateway_ws_connections_total`),
  `core:8001` і `auth:8002` (`http_requests_total`, `scan_*` — на core),
  `worker:9091` (скан-процеси). `/metrics` віддає: `http_requests_total`
  (method, path-баcket, status), `scan_duration_seconds` (histogram),
  `scan_results_total` (status, risk_level), `scan_services_total`.
- **Grafana** — профільно provisioned дашборд `monitoring/grafana/provisioning`
  (джерело Prometheus + панелі трафіку, тривалості скан-запусків, ризиків);
  `http://localhost:3000` (admin/admin).
- **Structured logs** — `LOG_JSON=true` перемикає логери на JSON-формат
  (`ts, level, logger, message` + додаткові поля).
- **OpenTelemetry** — `TRACING_ENABLED=true` + `OTLP_ENDPOINT` підключає
  експортер OTLP (HTTP); worker тегає спани `scan.run` (scan.id, host, outcome, risk).
