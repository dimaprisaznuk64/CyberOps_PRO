# CyberOps PRO — Demo

Скрипт `scripts/demo.py` проходить весь флоу через API Gateway
(чистий Python, stdlib, без залежностей).

## Кроки demo

1. `GET /health` — перевірка gateway.
2. register (role=analyst) → login → JWT access token.
3. Створення asset (host — ціль сканування).
4. Старт сканування (`POST /scans`, Celery → Nmap), опитування статусу.
5. Список findings → AI-пояснення першої знахідки (`POST /findings/{id}/explain`).
6. Генерація звіту (`POST /reports`, `report_type=scan`).
7. `GET /dashboard` — підсумкова статистика.

## Запуск

З Docker-стеком:

```bash
docker compose up -d --build
python scripts/demo.py
```

З Security Lab (ціль `vulnerable-api` — той самий docker network, сканування
знаходить реальні findings):

```bash
docker compose up -d --build
docker compose -f security-lab/docker-compose.yml up -d --build
python scripts/demo.py --host vulnerable-api
```

Опції: `--base` (URL gateway), `--username`/`--password` (або задати свої),
`--host` (ціль), `--wait` (сек, скільки чекати scan).

Приклад вихідних даних (фрагмент):

```
[5/7] start scan
      scan #12 queued
      status=running
      status=done
[6/7] findings + AI explanation
      2 findings, first: high — Telnet відкритий
      AI (rule): Виявлено: Telnet відкритий. Сервіс telnet на порту 23/tcp доступний і може бути атакований.
      risk:   Рівень ризику — HIGH (навчальний score 7 з 10: ...)
DONE
```

> Якщо worker не запущено або ціль недосяжна, demo працює далі й показує
> "no findings yet" — не падає.