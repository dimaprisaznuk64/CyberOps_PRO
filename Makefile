.PHONY: up down logs logs-worker test lint build migrate

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f backend

logs-worker:
	docker compose logs -f worker

test:
	cd backend && python -m pytest tests -q

lint:
	cd backend && python -m ruff check app tests ../workers ../services

build:
	docker compose build

migrate:
	cd backend && alembic upgrade head
