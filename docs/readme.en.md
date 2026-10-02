# CyberOps Platform PRO

Self-hosted platform for monitoring **your own** infrastructure: controlled Nmap scanning, findings with risk scoring, RBAC, real-time dashboard and alerts.

> ⚠️ Scan only your own machines, a private network, or the bundled `security-lab/`. The scanner refuses non-private addresses.

## Features
- JWT auth, refresh tokens, roles `user` / `analyst` / `admin`, per-role data visibility
- Assets and scans: Celery + Redis workers run Nmap, results parsed into services, CPE and findings
- Risk score per finding and per asset (current + historical max)
- Reports (PDF/CSV export), audit log, notifications (in-app, Email/SMTP, Telegram)
- WebSocket real-time dashboard, AI assistant that explains findings
- Next.js UI, English and Ukrainian

## Stack
Python 3.13 · FastAPI · SQLAlchemy (async) · PostgreSQL · Alembic · Celery · Redis · RabbitMQ · API Gateway · Next.js 15 / React 19 / TypeScript · Docker Compose · Kubernetes (kustomize) · Terraform (AWS) · GitHub Actions · Prometheus · Grafana · Jaeger (OpenTelemetry)

## Architecture
Browser → Gateway → `core` and `auth` services → PostgreSQL. Scans go through Celery workers (Redis broker), events through RabbitMQ, metrics and traces to Prometheus, Grafana and Jaeger. Details: [architecture.md](architecture.md).

## Quick start
```bash
cp .env.example .env
make up            # docker compose up -d --build
python scripts/demo.py   # end-to-end demo through the gateway
```
- UI: http://localhost:3000 · API (gateway): http://localhost:8000
- Vulnerable targets to scan: `make up-lab`, then `python scripts/demo.py --host vulnerable-api`
- Production-like run (required secrets): `make up-prod`

## Tests and quality
```bash
make test   # backend: 268 pytest tests
make lint   # ruff
cd frontend && npm ci && npm run typecheck && npm run build
```
CI (GitHub Actions): lint, tests, image build to GHCR, kind-based Kubernetes E2E, prod-compose E2E.

## Docs
- [Architecture](architecture.md) · [Deployment](deployment.md) · [Demo](demo.md) · [Roadmap](roadmap.md)
- [Повний довідник українською: історія v0.1–v1.16, API, K8s, Terraform](../README.md)
