.PHONY: up down logs logs-core logs-auth logs-gateway logs-worker test lint build migrate demo up-lab down-lab up-prod down-prod config-prod

up:
	docker compose up -d --build

down:
	docker compose down

# Віддалений/публічний запуск: обов'язкові секрети, обмежені логи, APP_ENV=prod
up-prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

down-prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml down

config-prod:
	JWT_SECRET="$${JWT_SECRET:-ci-fixture-secret-value-not-used-anywhere-32}" \
	POSTGRES_PASSWORD="$${POSTGRES_PASSWORD:-ci-fixture}" \
	ADMIN_PASSWORD="$${ADMIN_PASSWORD:-ci-fixture}" \
	CORS_ORIGINS="$${CORS_ORIGINS:-http://localhost:3000}" \
	NEXT_PUBLIC_API_URL="$${NEXT_PUBLIC_API_URL:-http://localhost:8000}" \
	GRAFANA_ADMIN_PASSWORD="$${GRAFANA_ADMIN_PASSWORD:-ci-fixture}" \
	docker compose -f docker-compose.yml -f docker-compose.prod.yml config -q

up-lab:
	docker compose -f security-lab/docker-compose.yml up -d --build

down-lab:
	docker compose -f security-lab/docker-compose.yml down

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

# З корня, щоб перевірка збігалася з gate у ci.yml: один конфіг (ruff.toml),
# один набір шляхів. Раніше тут був інший виклик, ніж у CI, — обидва були зелені
# на різних наборах файлів (v1.25).
lint:
	python -m ruff check backend gateway workers services scripts --exclude .kilo

build:
	docker compose build

migrate:
	cd backend && alembic upgrade head

demo:
	python scripts/demo.py