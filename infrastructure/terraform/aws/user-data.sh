#!/usr/bin/env bash
# Cloud-init скрипт (user-data) для EC2: Docker + застосунок через docker compose.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

REPO_URL="${repo_url}"
REPO_BRANCH="${repo_branch}"
JWT_SECRET="${jwt_secret}"
ADMIN_PASSWORD="${admin_password}"
APP_PUBLIC_URL="${app_public_url}"

apt-get update -y
apt-get install -y --no-install-recommends docker.io docker-compose-v2 git

systemctl enable --now docker

mkdir -p /opt
cd /opt
rm -rf cyberops
git clone --branch "$REPO_BRANCH" "$REPO_URL" cyberops
cd cyberops

# Публічна адреса потрібна двічі: NEXT_PUBLIC_APIURL вшивається у фронтенд
# під час збірки, а CORS_ORIGINS — це allow-list origin'ів на gateway.
# Terraform знає EIP, але інстанс доставляється РАНІШЕ, ніж EIP до нього
# присвоєно, тому за замовчуванням визначаємо адресу самі. Гонка з EIP
# реальна: якщо checkip поверне тимчасовий auto-assigned IP, той помре
# після присвоєння EIP — тому краще передати -var app_public_url=... (README).
imds_ipv4() {
  token="$(curl -fsS --max-time 3 -X PUT -H 'X-aws-ec2-metadata-token-ttl-seconds: 60' \
    http://169.254.169.254/latest/api/token || true)"
  [ -n "$token" ] || return 1
  curl -fsS --max-time 3 -H "X-aws-ec2-metadata-token: $token" \
    http://169.254.169.254/latest/meta-data/public-ipv4 || true
}

if [ -z "$APP_PUBLIC_URL" ]; then
  DETECTED="$(curl -fsS --max-time 5 http://checkip.amazonaws.com || true)"
  [ -n "$DETECTED" ] || DETECTED="$(imds_ipv4 || true)"
  DETECTED="$(printf '%s' "$DETECTED" | tr -d '[:space:]')"
  if [ -n "$DETECTED" ]; then
    APP_PUBLIC_URL="http://$DETECTED"
  else
    # Не зупиняємо деплой: API й так буде доступний, а фронтенд просто
    # не зможе дотягнутися до бекенду, поки його не переналаштувати.
    APP_PUBLIC_URL="http://localhost"
    echo "WARNING: не зміг визначити публічну адресу інстансу" >&2
    echo "WARNING: запустіть scripts/remote-configure.sh <user@host> http://<ip>" >&2
  fi
fi

[ -f .env ] || cp .env.example .env
sed -i "s|^JWT_SECRET=.*|JWT_SECRET=$JWT_SECRET|" .env
sed -i "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=$ADMIN_PASSWORD|" .env
sed -i "s|^NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=$APP_PUBLIC_URL:8000|" .env
sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=$APP_PUBLIC_URL:3000|" .env
sed -i "s|^APP_BASE_URL=.*|APP_BASE_URL=$APP_PUBLIC_URL:3000|" .env

# Прод-override: обов'язкові секрети, обмеження логів, APP_ENV=prod.
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

echo "CyberOps deployed:"
echo "  API:   $APP_PUBLIC_URL:8000"
echo "  UI:    $APP_PUBLIC_URL:3000"
echo "  admin: $ADMIN_PASSWORD"
