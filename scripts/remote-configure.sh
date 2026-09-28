#!/usr/bin/env bash
# Перевести вже розгорнутий на EC2 стек на іншу публічну адресу (EIP, домен).
#
#   scripts/remote-configure.sh ubuntu@1.2.3.4 http://1.2.3.4
#   scripts/remote-configure.sh ubuntu@cyberops.example.com https://cyberops.example.com
#
# Навіщо: NEXT_PUBLIC_API_URL вшивається у фронтенд під час збірки. Якщо на
# першому boot інстанс не мав EIP (він доставляється після старту), фронтенд
# зібрався з чужим адресою і в браузері йде на localhost відвідувача. Скрипт
# перезаписує три змінні й перестворює контейнери — після цього UI живий.
set -euo pipefail

target="${1:-}"
url="${2:-}"

if [ -z "$target" ] || [ -z "$url" ]; then
  echo "usage: $(basename "$0") <user@host> <public-url-without-port>" >&2
  echo "  приклад: $(basename "$0") ubuntu@1.2.3.4 http://1.2.3.4" >&2
  exit 2
fi

url="${url%/}"

ssh "$target" bash -s -- "$url" <<'REMOTE'
set -euo pipefail
url="$1"
cd /opt/cyberops
sed -i "s|^NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=$url:8000|" .env
sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=$url:3000|" .env
sed -i "s|^APP_BASE_URL=.*|APP_BASE_URL=$url:3000|" .env
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
echo "Перенастроєно на $url"
echo "  API: $url:8000"
echo "  UI:  $url:3000"
REMOTE
