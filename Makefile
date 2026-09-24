.PHONY: up down logs logs-core logs-auth logs-gateway logs-worker test lint build migrate

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f gateway

logs-core:
	docker compose logs -f core

logs-auth:
	docker compose logs -f auth

logs-worker:
	docker compose logs -f worker

test:
	cd backend && python -m pytest tests -q

lint:
	cd backend && python -m ruff check app tests ../workers ../services ../gateway

build:
	docker compose build

migrate:
	cd backend && alembic upgrade head