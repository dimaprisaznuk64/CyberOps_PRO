FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /repo

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY workers/ workers/
COPY services/ services/

ENV PYTHONPATH=/repo/backend:/repo

CMD ["celery", "-A", "workers.celery_app", "worker", "--loglevel=info", "--pool=solo"]
