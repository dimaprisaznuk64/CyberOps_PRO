# CyberOps PRO — Архітектура

Навчальна cybersecurity-платформа: моніторинг ассетів, сканування (Nmap),
нотифікації, звіти та AI-пояснення знахідок.

## Компоненти

```
                ┌──────────────┐     /api/v1/auth, /api/v1/users,
   Frontend /   │ API Gateway  │───► /api/v1/audit-logs
   API-клієнт ─►│  (gateway/)  │
   (WS/HTTP)    └──────┬───────┘     решта /api/v1/*, /ws, /dashboard
                       │ ┌────────►  core (:8001)
                       │ └────────►  auth (:8002)
  ┌────────────────┐   └─────────►  ws relay → core /ws
  │ core (FastAPI) │──► PostgreSQL (SQLAlchemy async + Alembic)
  │ auth (FastAPI) │──► Redis      (realtime / cache / broker)
  │ worker (Celery)│──► RabbitMQ   (events: scan.*, finding.*, report.*)
  │ scanner (Nmap) │──► Prometheus / Grafana / OTel+Jaeger (за налаштуванням)
  └────────────────┘
```

| Компонент | Технологія | Порт | Роль |
|---|---|---|---|
| `gateway` | FastAPI + httpx | 8000 | маршрутизація, JWT-гейт, identity-заголовки |
| `backed app.main` (core) | FastAPI | 8001 | assets / scans / findings / reports / notifications / dashboard / ws / ai |
| `backend app.auth_app` (auth) | FastAPI | 8002 | register / login / refresh / roles / users |
| `worker` | Celery + Redis | 9091 (metrics) | запуск Nmap, парсинг, derive_findings, risk score |
| `services/scanner` | python-nmap | — | `build_command`, `run_nmap`, `parse_nmap_xml` |
| `monitoring` | Prometheus + Grafana | 9090 / 3001 | метрики й дашборди |

## Потоки даних

- **Авторизація:** Gateway перевіряє JWT централізовано, прокидає
  `X-User-Id/Role/Username` + `X-Forwarded-For` у сервіси.
- **Сканування:** `core` створює Scan → відправляє в Celery (Redis broker) →
  `worker` виконує Nmap → записує Services → `derive_findings` →
  `compute_risk_score` → подія `scan.completed` → WS-сповіщення.
- **Події:** `services/events.py` публікує в RabbitMQ exchange
  `cyberops.events` (`scan.created`, `finding.created`, `report.generated` …),
  споживачі — spовідомлення та audit.
- **Realtime:** `services/realtime.py` (Redis pub/sub або in-memory) →
  WebSocket `/ws`.
- **Audit:** `services/audit.py` перехоплює запити, пише `user/action/ip/ua`.
- **AI Assistant:** `services/ai_assistant.py` пояснює знахідку (rules/LLM).

## Безпека

RBAC (`user` / `analyst` / `admin`), ownership-перевірки у всіх read/write
ендпоінтах, refresh tokens, хешування паролів (argon2), корс-конфіг, ліміт
сканувань на приватніта пред-визначені хоста `SCAN_ALLOW_PUBLIC=false`,
навмисно вразливий стенд Security Lab привʼязаний тільки до `127.0.0.1`.

## Деплой-матриця

| Спосіб | Де | Див. |
|---|---|---|
| `docker compose` | локально | `docs/deployment.md` |
| Kubernetes (kustomize) | kind / кластер | `docs/deployment.md` |
| Terraform + AWS EC2 | cloud | `docs/deployment.md` |