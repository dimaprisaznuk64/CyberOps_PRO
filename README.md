# CyberOps Platform PRO

Платформа моніторингу власної інфраструктури: аутентифікація, RBAC,
управління цілями (assets), контрольоване сканування, аналіз ризиків,
web-dashboard.

> ⚠️ **Етичне правило:** сканування проводимо **тільки** власних машин,
> локальної мережі або спеціальних навчальних лабораторій (`security-lab/`).

## Статус версій

| Версія | Статус | Що входить |
|---|---|---|
| **0.1** | ✅ поточна | FastAPI, PostgreSQL, Alembic, JWT, RBAC (admin/analyst/user), реєстрація/логін, користувачі, тести, Docker |
| 0.2 | 🔜 | Docker-стек, Redis, Celery, базовий scanner (Nmap) |
| 0.3 | 📋 | Nmap-parser, Services, Findings, Risk Score |
| 0.4 | 📋 | RabbitMQ-події, Notifications, Reports, Audit Logs |
| 0.5 | 📋 | WebSocket, real-time dashboard, тести E2E |
| 0.6 | 📋 | Prometheus, Grafana, structured logs, OpenTelemetry |
| 0.7 | 📋 | Microservices, API Gateway |
| 0.8 | 📋 | Kubernetes, CI/CD |
| 0.9 | 📋 | Terraform, Cloud |
| 1.0 | 📋 | Security Lab, AI Assistant, документація, demo |

## Ролі (RBAC)

| Роль | Права |
|---|---|
| `user` | перегляд власних target і сканувань |
| `analyst` | запуск сканувань і перегляд findings |
| `admin` | керування користувачами та системою |

## Структура

```text
CyberOps_PRO/
├── backend/            # FastAPI + PostgreSQL + Alembic
├── frontend/           # Next.js / React (з 0.2+)
├── services/scanner/   # Nmap-сканер (з 0.2)
├── workers/            # Celery (з 0.2)
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

**З Docker:**

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

## API (v0.1)

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
| GET | `/health` | public |

Swagger: `http://localhost:8000/docs`
