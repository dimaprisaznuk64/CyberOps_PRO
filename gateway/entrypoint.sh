#!/bin/sh
# TLS термінується на gateway, якщо задано GATEWAY_TLS_CERTFILE + GATEWAY_TLS_KEYFILE.
# Без них сервіс слухає звичайний HTTP (типовий випадок: TLS вже на балансуванті
# перед gateway, всередині compose-мережі — http).
set -eu

# Ім'я змінної навмисно НЕ GATEWAY_PORT: kubelet сам підставляє в контейнер
# змінні для кожного Service цього namespace, і для Service з безіменним
# портом (gateway.yaml) ім'я виходить рівно GATEWAY_PORT зі значенням
# tcp://<ClusterIP>:<port> — тобто не число. На kind-E2E gateway через це
# падав у CrashLoopBackOff: uvicorn отримував --port 'tcp://10.96.49.219:8000'
# і виходив, не піднявши сервер.
set -- --host 0.0.0.0 --port "${GATEWAY_LISTEN_PORT:-8000}"

if [ -n "${GATEWAY_TLS_CERTFILE:-}" ] && [ -n "${GATEWAY_TLS_KEYFILE:-}" ]; then
  set -- "$@" \
    --ssl-certfile "$GATEWAY_TLS_CERTFILE" \
    --ssl-keyfile "$GATEWAY_TLS_KEYFILE" \
    --ssl-version "${GATEWAY_TLS_VERSION:-2}" \
    --ssl-ciphers "${GATEWAY_TLS_CIPHERS:-ECDHE+AESGCM:ECDHE+CHACHA20:ECDHE+AES256:ECDHE+AES128}"
  if [ -n "${GATEWAY_TLS_KEYFILE_PASSWORD:-}" ]; then
    set -- "$@" --ssl-keyfile-password "$GATEWAY_TLS_KEYFILE_PASSWORD"
  fi
  echo "gateway: TLS увімкнено (cert=$GATEWAY_TLS_CERTFILE, version=$GATEWAY_TLS_VERSION)"
else
  echo "gateway: TLS вимкнено, слухаю HTTP"
fi

exec uvicorn gateway.main:app "$@"
