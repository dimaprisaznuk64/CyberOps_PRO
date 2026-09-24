#!/usr/bin/env bash
# Cloud-init скрипт (user-data) для EC2: Docker + застосунок через docker compose.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

REPO_URL="${repo_url}"
REPO_BRANCH="${repo_branch}"
JWT_SECRET="${jwt_secret}"

apt-get update -y
apt-get install -y --no-install-recommends docker.io docker-compose-v2 git

systemctl enable --now docker

mkdir -p /opt
cd /opt
rm -rf cyberops
git clone --branch "$REPO_BRANCH" "$REPO_URL" cyberops
cd cyberops

[ -f .env ] || cp .env.example .env
sed -i "s|^JWT_SECRET=.*|JWT_SECRET=$JWT_SECRET|" .env

docker compose up -d --build

echo "CyberOps deployed: http://$(curl -s http://checkip.amazonaws.com):8000"