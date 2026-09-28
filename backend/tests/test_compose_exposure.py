"""Інваріанти compose-файлів: що має слухати 0.0.0.0, а що — ні.

Перевірка навмисно не дублює `docker compose config`: вона ловить саме
регресії, які легко впустити очима, — хтось додасть сервіс або змінить
порт, і Postgres/RabbitMQ/Grafana знову опиняться в публічному інтернеті
разом з gateway і UI.
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML приходить з uvicorn[standard]")

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.yml"
PROD_OVERRIDE = ROOT / "docker-compose.prod.yml"

# Єдині сервіси, до яких звертається браузер: gateway (API) і frontend (UI).
PUBLIC_SERVICES = {"gateway", "frontend"}


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
            parts = str(spec).split(":")
            assert len(parts) in (2, 3), f"незрозумілий порт: {spec}"
            host_ip = parts[0] if len(parts) == 3 else None
            published, target = (parts[-2], parts[-1]) if host_ip else (parts[0], parts[1])
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
    frontend_args = services["frontend"]["build"]["args"]

    # ${VAR:?...} — compose зупиняється на старті, а не піднімає стек із
    # дефолтами dev-secret-change-me / admin/admin.
    assert ":?" in core["JWT_SECRET"]
    assert ":?" in core["ADMIN_PASSWORD"]
    assert ":?" in gateway["CORS_ORIGINS"]
    assert ":?" in frontend_args["NEXT_PUBLIC_API_URL"]
    assert services["postgres"]["environment"]["POSTGRES_PASSWORD"].startswith(
        "${POSTGRES_PASSWORD:?"
    )


def test_prod_override_restarts_containers_and_bounds_logs() -> None:
    services = _load(PROD_OVERRIDE)["services"]
    # Кожен сервіс має restart+logging: на EC2 після ребуту стек має
    # піднятися сам, а json-file без ліміту з'їдає диск і кладе весь compose.
    for name, service in services.items():
        assert service["restart"] == "unless-stopped", f"{name}: без restart policy"
        assert service["logging"]["options"]["max-size"], f"{name}: логи без ліміту"


def test_prod_override_does_not_publish_extra_ports() -> None:
    # Override не додає жодного ports: базовий файл уже тримає все
    # публічне в списку public, інакше compose їх склеїв би.
    for name, service in _load(PROD_OVERRIDE)["services"].items():
        assert not service.get("ports"), f"{name}: override не має публікувати порти"
