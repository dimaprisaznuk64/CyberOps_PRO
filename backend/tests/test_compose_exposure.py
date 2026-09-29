"""Інваріанти compose-файлів: що має слухати 0.0.0.0, а що — ні.

Перевірка навмисно не дублює `docker compose config`: вона ловить саме
регресії, які легко впустити очима, — хтось додасть сервіс або змінить
порт, і Postgres/RabbitMQ/Grafana знову опиняться у публічному інтернеті
разом з gateway і UI.

Файл читається як сирий YAML, тож підстановки змінних треба розібрати
власноруч — інакше `${POSTGRES_PORT:-5432}` розсипається на п'ять частин
через двокрапку всередині фігурних дужок.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML приходить з uvicorn[standard]")

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.yml"
PROD_OVERRIDE = ROOT / "docker-compose.prod.yml"

# Єдині сервіси, до яких звертається браузер: gateway (API) і frontend (UI).
PUBLIC_SERVICES = {"gateway", "frontend"}

# ${VAR}, ${VAR:-default}, ${VAR-default}, ${VAR:?err}, ${VAR?err}
_VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::?([-?])([^}]*))?\}")


def _substitute(text: str) -> str:
    """Підставляє значення за замовчуванням, як це робив би compose без .env.

    Для перевірки інваріантів цікавий саме дефолт: якщо порт не задано у .env
    (тобто на чистій машині чи в CI), саме він публікується назовні.

    `?` (на відміну від `-`) — не дефолт, а вимога задати змінну: compose зупиниться
    на старті. Підставляти сюди текст помилки безглуздо, тож він стає порожнім —
    і тест падає на `isdigit` з читабельним текстом замість мовчки прийнятого
    сміття.
    """

    def replace(match: re.Match) -> str:
        if match.group(2) == "-":
            return match.group(3)
        return ""

    return _VARIABLE.sub(replace, text)


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _published_ports(service: dict) -> list[tuple[str, int, str | None]]:
    """[(published, target, host_ip)]; host_ip=None означає 0.0.0.0 (усі інтерфейси)."""
    out: list[tuple[str, int, str | None]] = []
    for spec in service.get("ports") or []:
        if isinstance(spec, dict):  # compose зберігає словник у config-режимі
            out.append(
                (
                    str(spec.get("published")),
                    int(spec.get("target")),
                    spec.get("host_ip"),
                )
            )
        else:
            # "8000:8000" або "127.0.0.1:5432:5432"
            parts = _substitute(str(spec)).split(":")
            assert len(parts) in (2, 3), f"незрозумілий порт: {spec}"
            host_ip = parts[0] if len(parts) == 3 else None
            published, target = (parts[-2], parts[-1]) if host_ip else (parts[0], parts[1])
            assert target.isdigit(), f"порт має бути числом, а не {target!r}: {spec}"
            out.append((published, int(target), host_ip))
    return out


def test_compose_keeps_internal_services_off_the_internet() -> None:
    services = _load(COMPOSE)["services"]
    offenders = {
        name: ports
        for name, service in services.items()
        if name not in PUBLIC_SERVICES
        for ports in [_published_ports(service)]
        if ports and any(host_ip is None for _, _, host_ip in ports)
    }
    assert offenders == {}, f"сервіси мають слухати 0.0.0.0: {offenders}"


def test_gateway_and_frontend_are_published_for_browsers() -> None:
    services = _load(COMPOSE)["services"]
    for name, target in (("gateway", 8000), ("frontend", 3000)):
        ports = _published_ports(services[name])
        assert any(int(p) == target and host_ip is None for p, _, host_ip in ports), (
            f"{name}:{target} має бути доступний ззовні (host_ip=None)"
        )


def test_prod_override_requires_secrets_and_public_api_url() -> None:
    services = _load(PROD_OVERRIDE)["services"]
    core = services["core"]["environment"]
    gateway = services["gateway"]["environment"]
    frontend_env = services["frontend"]["environment"]

    # ${VAR:?...} — compose зупиняється на старті, а не піднімає стек із
    # дефолтами dev-secret-change-me / admin/admin.
    assert ":?" in core["JWT_SECRET"]
    assert ":?" in core["ADMIN_PASSWORD"]
    assert ":?" in gateway["CORS_ORIGINS"]
    assert ":?" in frontend_env["API_PUBLIC_URL"]
    assert services["postgres"]["environment"]["POSTGRES_PASSWORD"].startswith(
        "${POSTGRES_PASSWORD:?"
    )


def test_frontend_api_url_is_runtime_only_in_compose() -> None:
    """Адреса API має задаватися в рантаймі, а не вписуватися в образ.

    Регресія: NEXT_PUBLIC_* підставляється в бандл під час `next build`, тож
    образ, зібраний до появи EIP, назавжди ходив у адресу попереднього стенду.
    Симптом — порожній UI при повністю живому бекенді, тобто виглядає як
    «зламаний бекенд». Runtime-варіант (/runtime-config.js) переживає
    перенесення стенду без перебудови образу.
    """
    for label, path in (("compose", COMPOSE), ("prod", PROD_OVERRIDE)):
        service = _load(path)["services"]["frontend"]
        args = (service.get("build") or {}).get("args") or {}
        assert "NEXT_PUBLIC_API_URL" not in args, (
            f"{label}: адреса API знову передається як build-arg і буде вписана "
            "в бандл назавжди; їй місце лише в environment"
        )
    assert "API_PUBLIC_URL" in _load(COMPOSE)["services"]["frontend"]["environment"]


def test_frontend_dockerfile_has_no_baked_api_url_default() -> None:
    """`ENV NEXT_PUBLIC_API_URL=${ARG:-...}` зважує дефолт у бандл.

    Саме це і робило образ, зібраний у CI без .env, «зламаним» на kind:
    адреса з localhost потрапляла в JavaScript назавжди. Дефолту бути не
    має — вистачить порожнього значення, яке код трактує як «не задано».
    """
    dockerfile = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    match = re.search(r"^ENV NEXT_PUBLIC_API_URL=(.*)$", dockerfile, re.MULTILINE)
    assert match, "NEXT_PUBLIC_API_URL більше не задається у Dockerfile"
    assert ":-" not in match.group(1), (
        f"у Dockerfile знову з'явився дефолт адреси: {match.group(1)}"
    )


def test_k8s_cors_allows_the_frontend_origin() -> None:
    """Origin фронтенду має бути в CORS_ORIGINS, інакше браузер блокує API.

    Регресія: у k8s UI віддається на NodePort 30010, а CORS_ORIGINS містив
    лише :3000 (compose). На kind-стенді кожен запит з UI блокувався.
    Smoke-тест цього не бачить — curl не надсилає заголовок Origin, тож
    перевірка можлива тільки зіставленням маніфестів.
    """
    secret = _load(ROOT / "infrastructure/kubernetes/base/secret.yaml")
    cors = [o.strip() for o in secret["stringData"]["CORS_ORIGINS"].split(",") if o.strip()]
    services = {
        doc["metadata"]["name"]: doc
        for path in sorted((ROOT / "infrastructure/kubernetes/base").glob("*.yaml"))
        for doc in yaml.safe_load_all(path.read_text(encoding="utf-8"))
        if doc and doc.get("kind") == "Service"
    }
    node_ports = [
        port["nodePort"]
        for service in services.values()
        if service["metadata"]["name"] == "frontend"
        for port in service.get("spec", {}).get("ports") or []
        if port.get("nodePort")
    ]
    assert node_ports, "у frontend Service немає nodePort — звідки взяти origin?"
    for port in node_ports:
        assert f"http://localhost:{port}" in cors, (
            f"origin фронтенду з k8s (:{port}) немає в CORS_ORIGINS={cors}"
        )


def test_prod_override_restarts_containers_and_bounds_logs() -> None:
    services = _load(PROD_OVERRIDE)["services"]
    # Кожен довгоживучий сервіс має restart+logging: на EC2 після ребуту стек
    # має піднятися сам, а json-file без ліміту з'їдає диск і кладе весь
    # compose.
    for name, service in services.items():
        assert service["logging"]["options"]["max-size"], f"{name}: логи без ліміту"
        if name == "migrations":
            continue
        assert service["restart"] == "unless-stopped", f"{name}: без restart policy"


def test_migrations_are_a_one_shot_service_that_gates_the_others() -> None:
    """Міграції мають бути одноразовим сервісом, до якого йдуть решта.

    Регресія, знайдена на prod: у compose не було міграцій узагалі —
    `make migrate` виконує alembic на хості, а на свіжій машині після
    `make up-prod` таблиць не існувало. Бекенд піднімався, /health відповідав
    «ok», а система не працювала (і сид адміна падав на відсутній таблиці).

    Три речі мають бути одночасно, інакше одна з них знову зламається:
      * сервіс існує і виконує `alembic upgrade head`;
      * core/auth/worker чекають на `service_completed_successfully`
        (service_started пропустив би стенд із падінням міграцій);
      * `restart: "no"` — інакше prod-override з unless-stopped піднімає
        завершений контейнер по колу.
    """
    base = _load(COMPOSE)["services"]
    migrations = base["migrations"]
    assert migrations["command"] == ["alembic", "upgrade", "head"]
    assert migrations["restart"] == "no"
    assert (migrations["depends_on"]["postgres"]["condition"]) == "service_healthy"

    for name in ("core", "auth", "worker"):
        condition = (base[name]["depends_on"].get("migrations") or {}).get("condition")
        assert condition == "service_completed_successfully", (
            f"{name} не чекає на міграції: {condition!r}"
        )
    assert _load(PROD_OVERRIDE)["services"]["migrations"]["restart"] == "no"


def test_prod_override_does_not_publish_extra_ports() -> None:
    # Override не додає жодного ports: базовий файл уже тримає все
    # публічне в списку public, інакше compose їх склеїв би.
    for name, service in _load(PROD_OVERRIDE)["services"].items():
        assert not service.get("ports"), f"{name}: override не має публікувати порти"


def test_substitute_reads_compose_defaults() -> None:
    # Розбір списку портів тримається на цьому: без нього
    # "127.0.0.1:${POSTGRES_PORT:-5432}:5432" дає п'ять частин замість трьох
    # і перевірка падає на синтаксисі, а не на сенсі.
    assert _substitute("${POSTGRES_PORT:-5432}") == "5432"
    assert _substitute("${PORT}") == ""
    assert _substitute("127.0.0.1:${POSTGRES_PORT:-5433}:5432") == "127.0.0.1:5433:5432"
    # Службове повідомлення в ${VAR:?} не має підставлятись у порт.
    assert _substitute("${VAR:?must be set}") == ""


def test_postgres_publishes_only_a_loopback_port() -> None:
    postgres = _load(COMPOSE)["services"]["postgres"]
    ports = _published_ports(postgres)
    assert ports == [("5432", 5432, "127.0.0.1")], (
        f"postgres має публікувати лише 127.0.0.1 із внутрішнім 5432: {ports}"
    )
