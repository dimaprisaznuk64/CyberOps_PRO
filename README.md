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
| **0.5** | ✅ | WebSocket, real-time dashboard, тести E2E |
| 0.6 | 🔜 | Prometheus, Grafana, structured logs, OpenTelemetry |
| 0.5 | ✅ | WebSocket, real-time dashboard, тести E2E |
| 0.6 | ✅ | Prometheus, Grafana, structured logs, OpenTelemetry |
| 0.7 | 📋 | Microservices, API Gateway |
| 0.8 | 📋 | Kubernetes, CI/CD |
| 0.9 | 📋 | Terraform, Cloud |
| 1.0 | 📋 | Security Lab, AI Assistant, документація, demo |

## Ролі (RBAC)

| Роль | Права |
|---|---|
| `user` | перегляд власних asset і сканувань |
| `analyst` | запуск сканувань і перегляд findings |
| `admin` | керування користувачами та системою |

## Структура

```text
CyberOps_PRO/
├── backend/            # FastAPI + PostgreSQL + Alembic
├── frontend/           # Next.js / React (з 0.3+)
├── services/scanner/   # Nmap: build_command, run_nmap, parse_nmap_xml
├── workers/            # Celery worker (Redis broker)
├── security-lab/       # навчальні vulnerable-сервіси
├── monitoring/         # Prometheus, Grafana, Jaeger
├── infrastructure/     # docker, kubernetes, terraform
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
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

**З Docker (API + worker + Redis):**

```bash
docker compose up -d --build
```

**Перевірка:**

```bash
cd backend
python -m pytest tests -q       # тести
python -m ruff check app tests  # лінт
curl http://localhost:8000/health
```

## API (v0.6)

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

- **Prometheus** — `/metrics` віддає метрики: `http_requests_total`
  (method, path-баcket, status), `scan_duration_seconds` (histogram),
  `scan_results_total` (status, risk_level), `scan_services_total`.
- **Grafana** — профільно provisioned дашборд `monitoring/grafana/provisioning`
  (джерело Prometheus + панелі трафіку, тривалості скан-запусків, ризиків);
  `http://localhost:3000` (admin/admin).
- **Structured logs** — `LOG_JSON=true` перемикає логери на JSON-формат
  (`ts, level, logger, message` + додаткові поля).
- **OpenTelemetry** — `TRACING_ENABLED=true` + `OTLP_ENDPOINT` підключає
  експортер OTLP (HTTP); worker тегає спани `scan.run` (scan.id, host, outcome, risk).
