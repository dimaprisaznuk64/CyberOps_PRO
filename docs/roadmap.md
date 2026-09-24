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

## Фікси після введення в експлуатацію

- `dcf3a56` — frontend: `/health` повертає `services` словником, не масивом → render `Object.entries`.
- `8500c07` — worker: SQLAlchemy async-пул не можна перевикористовувати між Celery-тасками (`asyncio.run` на кожен таск) → окремий engine з `NullPool`. Симптом: «Task attached to a different loop» на 2-му сканi, scan зависає у `pending`.

## Відомі незакриті пункти плану (наступні пріоритети)

- **#14 Notifications канали** — зараз лише web (таблиця notifications). Додати:
  - Email-сповіщення (SMTP) для high/critical findings;
  - Telegram bot (асинхронно через Celery-таск, щоб не вантажити API);
  - поле `channel` (web/email/telegram) + налаштування в Settings.
- **#16 App Security** — зараз тільки edge-валідація та RBAC. Додати:
  - rate limiting на Gateway (login/register — до 5/хв, API — per-IP/token bucket);
  - CI-сканування: Bandit (Python), pip-audit (залежності), Trivy (Docker-образи), Semgrep (ruleset py);
  - hardening: ciphers/HTTP headers у gateway.
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
python -m ruff check app tests ../workers ../services ../gateway   # backend/.venv
cd backend && python -m pytest tests -q # тести (73)
cd frontend && npm run build && npx tsc --noEmit
```