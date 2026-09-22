.PHONY: up down logs test lint build

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f backend

test:
	cd backend && python -m pytest tests -q

lint:
	cd backend && python -m ruff check app tests

build:
	docker compose build
