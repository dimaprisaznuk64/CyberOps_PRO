# FastAPI + PostgreSQL + JWT + RBAC backend

## Розробка

```bash
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
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
