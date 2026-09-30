#!/usr/bin/env bash
#
# Перевірки поведінки стенду: не «процеси піднялися», а «симою можна
# скористатися». Спільний для kind (deploy.yml) і compose-prod (prod-e2e.yml),
# щоб два стенди не розходилися змінами — дубльований smoke-тест розходиться
# з першою ж правкою, а байдужість до цього й призводила до багів, які
# ховалися за «усе зелене».
#
# Обов'язкові змінні:
#   GATEWAY_URL      — адреса gateway (те, куди ходить браузер)
#   FRONTEND_URL     — адреса UI
#   EXPECTED_API_URL — що /runtime-config.js має віддати; береться з
#                      ConfigMap або compose env, а не з константи тут,
#                      інакше тест підтверджував би себе самого
#   EXPECTED_ORIGIN  — origin фронтенду для CORS-перевірки
#   ADMIN_USER/ADMIN_PASS
#   PROMETHEUS_URL   — адреса Prometheus; таргети скрейпу мають бути up
#   JAEGER_URL       — адреса query-сервісу Jaeger (UI/API, 16686)
#   GRAFANA_URL      — адреса Grafana
#   GRAFANA_USER/GRAFANA_PASS — для її API
#   EXPECTED_TRACE_SERVICES — через пробіл service.name, які мають бути
#                      видні в Jaeger після запитів вище. ОБОВ'ЯЗКОВО
#                      визначається воркфлоу з розгорнутого стенду
#                      (Deployment / живий контейнер), а не пишеться
#                      константою: Jaeger групує спани за service.name, і
#                      хардкод зеленіє рівно тоді, коли сервіс перейменовано
#
# Спостерігальність теж обов'язкова, а не опційна. «Процеси піднялися» ще не
# означає «моніторинг їх бачить»: до v1.16 жоден стенд не перевіряв, що
# Prometheus має хоч один таргет up, а в Jaeger прибув хоч один спан. Саме так
# і жив баг з недоступним jaeger:14269 у k8s — конфіг виглядав правильним.
#
# Опційно: SMOKE_ASSET_NAME (типово kind-e2e), ADMIN_LOGIN_ATTEMPTS (12),
# OBS_ATTEMPTS (30).

set -euo pipefail

: "${GATEWAY_URL:?GATEWAY_URL обов'язковий}"
: "${FRONTEND_URL:?FRONTEND_URL обов'язковий}"
: "${EXPECTED_API_URL:?EXPECTED_API_URL обов'язковий}"
: "${EXPECTED_ORIGIN:?EXPECTED_ORIGIN обов'язковий}"
: "${ADMIN_USER:?ADMIN_USER обов'язковий}"
: "${ADMIN_PASS:?ADMIN_PASS обов'язковий}"
: "${PROMETHEUS_URL:?PROMETHEUS_URL обов'язковий}"
: "${JAEGER_URL:?JAEGER_URL обов'язковий}"
: "${GRAFANA_URL:?GRAFANA_URL обов'язковий}"
: "${GRAFANA_USER:?GRAFANA_USER обов'язковий}"
: "${GRAFANA_PASS:?GRAFANA_PASS обов'язковий}"
: "${EXPECTED_TRACE_SERVICES:?EXPECTED_TRACE_SERVICES обов'язковий}"

ASSET_NAME="${SMOKE_ASSET_NAME:-kind-e2e}"
LOGIN_ATTEMPTS="${ADMIN_LOGIN_ATTEMPTS:-12}"
OBS_ATTEMPTS="${OBS_ATTEMPTS:-30}"

# Очікування готовності. Один запит на старті — лотерея: контейнер може ще
# слухати, а може вже впасти. Тому спершу діждемося відповіді, і лише потім
# перевірятимемо зміст.
wait_for() {
  local url=$1 name=$2
  for _ in $(seq 1 60); do
    if curl -fsS -o /dev/null "$url" 2>/dev/null; then
      return 0
    fi
    sleep 2
  done
  echo "::error::$name не відповів за 120 с: $url"
  return 1
}

echo "--- очікування готовності"
wait_for "$GATEWAY_URL/health" gateway
wait_for "$FRONTEND_URL/runtime-config.js" frontend

echo "--- gateway /health"
curl -fsS "$GATEWAY_URL/health"
echo

echo "--- frontend /runtime-config.js (очікується $EXPECTED_API_URL)"
CONFIG=$(curl -fsS "$FRONTEND_URL/runtime-config.js")
echo "$CONFIG"
# Саме головна перевірка: адреса має прийти з контейнера, а не з бандлу.
# Якщо образ зібрали з build-arg, значення впечетуються в JavaScript назавжди,
# і перенесення стенду ламає UI, не торкаючись бекенду.
grep -qF "\"$EXPECTED_API_URL\"" <<<"$CONFIG" || {
  echo "::error::runtime-конфіг не містить $EXPECTED_API_URL"; exit 1;
}

echo "--- CORS: origin $EXPECTED_ORIGIN має бути дозволений"
# Без цього кроку E2E зелений при заблокованому UI: curl не надсилає Origin,
# тож неправильний CORS_ORIGINES непомітний. Обов'язково OPTIONS з Origin —
# так само, як робить браузер перед POST /login.
ALLOW=$(curl -sS -o /dev/null -D - -X OPTIONS "$GATEWAY_URL/api/v1/auth/login" \
  -H "Origin: $EXPECTED_ORIGIN" \
  -H "Access-Control-Request-Method: POST" \
  | tr -d '\r' | grep -i '^access-control-allow-origin:' | awk '{print $2}' || true)
echo "allow-origin: ${ALLOW:-<none>}"
[ "$ALLOW" = "$EXPECTED_ORIGIN" ] || {
  echo "::error::CORS не дозволяє origin фронтенду $EXPECTED_ORIGIN"; exit 1;
}

echo "--- вхід: $ADMIN_USER"
# Повторюємо: сид адміністратора сам чекає на міграції з повторами, тож одразу
# після deploy він може ще не відпрацювати. Спроб обмежено, і наприкінці
# падіння все одно голосне — це прибирає гонку, не приховуючи поломку.
TOKEN=""
for attempt in $(seq 1 "$LOGIN_ATTEMPTS"); do
  RESPONSE=$(curl -sS -w '\n%{http_code}' -X POST "$GATEWAY_URL/api/v1/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}" || true)
  CODE=$(tail -n1 <<<"$RESPONSE")
  if [ "$CODE" = 200 ]; then
    TOKEN=$(head -n -1 <<<"$RESPONSE" | jq -r '.access_token // empty')
    [ -n "$TOKEN" ] && break
  fi
  echo "  спроба $attempt: HTTP $CODE"
  sleep 5
done
[ -n "$TOKEN" ] || {
  echo "::error::не вдалося увійти після $LOGIN_ATTEMPTS спроб — див. admin_seed_* у логах auth"; exit 1;
}
echo "увійшли з спробою $attempt"
LOGIN_ATTEMPT_USED=$attempt

echo "--- створення активу і читання назад"
CODE=$(curl -sS -o /dev/null -w '%{http_code}' -X POST "$GATEWAY_URL/api/v1/assets" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"name\":\"$ASSET_NAME\",\"host\":\"127.0.0.1\"}")
echo "create asset: HTTP $CODE"
[ "$CODE" = 201 ] || { echo "::error::актив не створився (HTTP $CODE)"; exit 1; }

FOUND=$(curl -fsS "$GATEWAY_URL/api/v1/assets" -H "Authorization: Bearer $TOKEN" \
  | jq -r --arg n "$ASSET_NAME" '[.[] | select(.name==$n)] | length')
echo "знайдено активів $ASSET_NAME: $FOUND"
[ "$FOUND" -ge 1 ] || { echo "::error::створений актив не читається назад"; exit 1; }

echo "--- Prometheus: усі таргети скрейпу мають бути up"
# Стейл піднімається, а Prometheus потім може роками смикати неіснуючий порт
# і показувати «DOWN» — без цієї перевірки це не видно ніде: в UI дашборду
# просто порожні панелі. Список таргетів беремо з самого Prometheus, а не
# з константи тут, інакше тест підтверджував би себе сам.
# Даємо час: інтервал скрейпу 15 с, тож одразу після старту все ще "connecting".
DOWN=""
for attempt in $(seq 1 "$OBS_ATTEMPTS"); do
  DOWN=$(curl -fsS "$PROMETHEUS_URL/api/v1/targets" 2>/dev/null \
    | jq -r '.data.activeTargets[] | select(.health != "up")
             | "\(.labels.job) -> \(.scrapeUrl): \(.lastError // "unknown")"' || true)
  [ -z "$DOWN" ] && break
  echo "  спроба $attempt: не всі таргети up"
  sleep 4
done
echo "стан усіх таргетів:"
curl -fsS "$PROMETHEUS_URL/api/v1/targets" \
  | jq -r '.data.activeTargets[] | "  \(.labels.job)\t\(.health)\t\(.scrapeUrl)"'
[ -z "$DOWN" ] || { echo "::error::не всі таргети Prometheus up:"; echo "$DOWN"; exit 1; }

echo "--- Jaeger: очікуємо спани від $EXPECTED_TRACE_SERVICES"
# Запити вище вже пройшли через gateway, core і auth, тож їхні спани мали
# дійти через OTLP. Якщо їх немає — або немає колектора, або OTLP_ENDPOINT
# веде не туди. До v1.16 це ніхто не перевіряв: трасування з v1.3 було
# увімкнено скрізь, але "увімкнено" і "працює" — різні речі.
MISSING=""
for attempt in $(seq 1 "$OBS_ATTEMPTS"); do
  SERVICES=$(curl -fsS "$JAEGER_URL/api/services" 2>/dev/null \
    | jq -r '.data[]?' || true)
  MISSING=""
  for want in $EXPECTED_TRACE_SERVICES; do
    grep -qxF "$want" <<<"$SERVICES" || MISSING="$MISSING $want"
  done
  [ -z "$MISSING" ] && break
  echo "  спроба $attempt: не знайдено:$MISSING (є: ${SERVICES:-<none>})"
  sleep 4
done
echo "сервіси в Jaeger: ${SERVICES:-<none>}"
[ -z "$MISSING" ] || {
  echo "::error::у Jaeger немає сервісів:$MISSING — OTLP-спани не доходять"; exit 1;
}

echo "--- Jaeger: спани реально читаються, а не лише імена сервісів"
# /api/services показує лише ім'я. Справжня перевірка — дістати хоч один
# спан за цим сервісом: інакше сервіс може зареєструватись, а дані
# не прийшлись (наприклад, експорт впав на серіалізації).
TRACE=$(curl -fsS --get "$JAEGER_URL/api/traces" \
  --data-urlencode "service=$(echo "$EXPECTED_TRACE_SERVICES" | awk '{print $1}')" \
  --data-urlencode "lookback=1h" --data-urlencode "limit=1" 2>/dev/null || true)
TRACE_COUNT=$(jq -r '.data | length' <<<"$TRACE" 2>/dev/null || echo 0)
echo "спанів знайдено: $TRACE_COUNT"
[ "$TRACE_COUNT" -ge 1 ] || {
  echo "::error::сервіс є в /api/services, але жодного спана не читається"; exit 1;
}

echo "--- Grafana: датасорс Prometheus має бути provisionований і здоровий"
# Provisioning мовчки ламається, якщо URL не резолвиться або ConfigMap-key
# монтується не туди (був такий баг із "/"). Grafana при цьому радосно
# віддає /api/health=ok, тож перевіряти треба саме датасорс.
DS_OK=""
for attempt in $(seq 1 "$OBS_ATTEMPTS"); do
  DS_JSON=$(curl -fsS -u "$GRAFANA_USER:$GRAFANA_PASS" "$GRAFANA_URL/api/datasources" 2>/dev/null || true)
  DS_OK=$(jq -r '[.[] | select(.type == "prometheus")] | length' <<<"$DS_JSON" 2>/dev/null || echo 0)
  [ "${DS_OK:-0}" -ge 1 ] && break
  echo "  спроба $attempt: датасорс Prometheus ще не provisionований"
  sleep 4
done
echo "датасорсів Prometheus: ${DS_OK:-0}"
[ "${DS_OK:-0}" -ge 1 ] || {
  echo "::error::Grafana не має provisionованого датасорса Prometheus"; exit 1;
}

echo "--- Grafana: датасорс бачить дані (health, а не лише існування)"
DS_UID=$(jq -r '.[] | select(.type == "prometheus") | .uid' <<<"$DS_JSON" | head -n1)
DS_HEALTH=$(curl -fsS -u "$GRAFANA_USER:$GRAFANA_PASS" \
  "$GRAFANA_URL/api/datasources/uid/$DS_UID/health" 2>/dev/null || true)
DS_STATUS=$(jq -r '.status // "unknown"' <<<"$DS_HEALTH" 2>/dev/null || echo unknown)
echo "датасорс $DS_UID: $DS_STATUS"
[ "$DS_STATUS" = "OK" ] || {
  echo "::error::Grafana-датасорс Prometheus не здоровий ($DS_STATUS) — provisioning створив його, але дані не йдуть"; exit 1;
}

echo "::group::підсумок"
echo "runtime-config: $EXPECTED_API_URL"
echo "CORS origin:    $ALLOW"
echo "вхід:           $ADMIN_USER, спроба $LOGIN_ATTEMPT_USED"
echo "актив $ASSET_NAME: створено і прочитано"
echo "Prometheus:     усі таргети up"
echo "Jaeger:         спани є (${EXPECTED_TRACE_SERVICES})"
echo "Grafana:        датасорс Prometheus $DS_STATUS"
echo "::endgroup::"
echo "SMOKE OK"
