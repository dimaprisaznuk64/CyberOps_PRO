# FastAPI + PostgreSQL + JWT + RBAC backend

Проєкт розділено на два сервіси (v0.7), які виконуються як окремі процеси:

- **core** (aсets, scans, findings, notifications, reports, dashboard, ws): `uvicorn app.main:app --port 8001`
- **auth** (auth, users, audit-logs): `uvicorn app.auth_app:app --port 8002`

У compose перед ними стоїть **API Gateway** (см. `../gateway`), який слухає
порт 8000 і маршрутизує запити за префіксом.

## Розробка

```bash
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --reload                # core (порт 8001)
uvicorn app.auth_app:app --reload --port 8002  # auth (порт 8002)
# API Gateway локально:
cd .. && pip install -r gateway/requirements.txt
uvicorn gateway.main:app --reload --port 8000
```

## Тести

```bash
python -m pytest tests -q
python -m ruff check app tests
```

## Міграції

```bash
alembic upgrade head
alembic revision --autogenerate -m "msg"
```
