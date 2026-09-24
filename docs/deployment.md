# CyberOps PRO — Деплой

Три способи запуску: Docker Compose (локально), Kubernetes + kind, Terraform + AWS.

## 1. Docker Compose (швидкий старт)

```bash
cp .env.example .env
docker compose up -d --build
```

Сервіси: `gateway :8000`, `core :8001`, `auth :8002`, `worker`, `postgres :5432`,
`redis :6379`, `rabbitmq :5672 (+15672)`, `prometheus :9090`, `grafana :3000`.

Перевірка:

```bash
curl http://localhost:8000/health   # {"status":"ok",...}
make test && make lint
```

## 2. Kubernetes (kind)

Маніфести — `infrastructure/kubernetes/` (kustomize base + overlay) і validated
у CI. Обʼєкти: Namespace `cyberops`, Deployments (core, auth, gateway, worker,
postgres, redis, rabbitmq, prometheus, grafana), Jobs (migrations), PVC,
NodePort (gateway 30080, grafana 30300).

```bash
docker compose build
kind create cluster
kind load docker-image cyberops/cyberops-backend:latest cyberops/cyberops-worker:latest cyberops/cyberops-gateway:latest
kubectl apply -k infrastructure/kubernetes/overlays/dev
kubectl -n cyberops wait --for=condition=complete job/migrations --timeout=240s
kubectl -n cyberops rollout status deploy/gateway --timeout=240s
kubectl -n cyberops port-forward svc/gateway 8000:8000
```

Проверка: `curl http://localhost:8000/health`.

## 3. Terraform + AWS (cloud)

Модуль — `infrastructure/terraform/aws/` (EC2 Ubuntu 22.04 + SG + EIP;
user-data ставить Docker і розгортає стек з Git).

```bash
cd infrastructure/terraform/aws
terraform init
terraform plan -var key_name=my-key
terraform apply -var key_name=my-key
```

Outputs: `public_ip`, `ssh_command`, `gateway_url` (`http://<ip>:8000`).

> Для продакшену: управляний PostgreSQL, образ через GHCR, ingress + TLS.

## CI/CD (GitHub Actions)

- `ci.yml` — тести + ruff + compose/kustomize валідація (на кожен push).
- `docker.yml` — збірка образів і push до GHCR (push на `master` → `dev`,
  теги `v*` → версія).
- `deploy.yml` — kind E2E: збірка → кластер → `kubectl apply -k` →
  wait migrations/jobs → smoke `/health`.

Образи: `ghcr.io/<owner>/<repo>/cyberops-{backend,worker,gateway}:<tag>`.