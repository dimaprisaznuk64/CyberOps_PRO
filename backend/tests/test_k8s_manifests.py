"""Інваріанти k8s-манифестів: хто має доступ до Secret, а що — ні.

Натхнення — `test_compose_exposure.py`: CI перевіряє лише `kubectl kustomize`,
тобто синтаксис. Регресія, яку вона не бачить: ключ перенесли з ConfigMap у
Secret, а якийсь контейнер забув підключити Secret — маніфест лишається
валідним, Job падає вже на стенді. Саме так v1.12 зламав `migrations`:
`DATABASE_URL` переїхав у Secret, а Job мав лише `configMapRef`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML приходить з uvicorn[standard]")

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "infrastructure" / "kubernetes" / "base"
OVERLAYS = ROOT / "infrastructure" / "kubernetes" / "overlays"
CONFIGMAP = BASE / "configmap.yaml"
SECRET = BASE / "secret.yaml"

# Наші сервіси + Job міграцій. Усі мають читати DATABASE_URL, тобто Secret.
APP_WORKLOADS = ("core", "auth", "worker", "gateway", "migrations")

# Ключі, які ніколи не повертаються у ConfigMap: у DATABASE_URL є пароль, а
# CORS_ORIGINS="*" вимикає перевірку origin повністю.
SECRET_ONLY_KEYS = ("DATABASE_URL", "CORS_ORIGINS")


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _documents(path: Path) -> list[dict[str, Any]]:
    return [doc for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")) if doc]


def _containers(doc: dict[str, Any]) -> list[dict[str, Any]]:
    spec = doc.get("spec", {})
    template = spec.get("template", spec)
    return (template.get("spec") or {}).get("containers") or []


def _find_workload(path: Path, name: str) -> dict[str, Any]:
    for doc in _documents(path):
        meta = doc.get("metadata", {})
        if meta.get("name") == name and doc.get("kind") in {
            "Deployment",
            "StatefulSet",
            "DaemonSet",
            "Job",
            "CronJob",
        }:
            return doc
    raise AssertionError(f"{name}: не знайдено в {path.name}")


def test_app_workloads_import_the_secret() -> None:
    """Без secretRef контейнер не бачить DATABASE_URL — і бере дефолт із
    config.py, тобто рядок на localhost, і падає з connection refused."""
    missing: dict[str, list[str]] = {}
    for name in APP_WORKLOADS:
        path = BASE / f"{name}.yaml"
        doc = _find_workload(path, name)
        refs: list[str] = []
        for container in _containers(doc):
            for source in container.get("envFrom") or []:
                if "secretRef" in source:
                    refs.append(source["secretRef"]["name"])
        if not refs:
            missing[name] = ["envFrom.secretRef"]
    assert missing == {}, f"контейнери без Secret: {missing}"


def test_app_workloads_import_the_configmap() -> None:
    """Секрет не замінює конфіг: APP_ENV, URL сервісів, ліміти лишаються
    у ConfigMap, тож обидва envFrom обов'язкові."""
    missing: dict[str, list[str]] = {}
    for name in APP_WORKLOADS:
        path = BASE / f"{name}.yaml"
        doc = _find_workload(path, name)
        refs: list[str] = []
        for container in _containers(doc):
            for source in container.get("envFrom") or []:
                if "configMapRef" in source:
                    refs.append(source["configMapRef"]["name"])
        if not refs:
            missing[name] = ["envFrom.configMapRef"]
    assert missing == {}, f"контейнери без ConfigMap: {missing}"


def test_secret_only_keys_are_not_in_configmap() -> None:
    data = _load(CONFIGMAP).get("data") or {}
    found = {key: data[key] for key in SECRET_ONLY_KEYS if key in data}
    assert found == {}, f"секрети в ConfigMap (ConfigMap не шифрований): {found}"


def test_cors_origins_is_not_a_wildcard() -> None:
    value = (_load(SECRET).get("stringData") or {}).get("CORS_ORIGINS", "")
    assert value != "*", 'CORS_ORIGINS="*" вимикає перевірку origin'
    assert value.strip(), "порожній CORS_ORIGINS краще, ніж зірочка: жоден origin"


def test_secret_declares_every_key_the_workloads_need() -> None:
    """Якщо ключ є в ConfigMap або манифесті, але не в Secret — контейнер
    підставить дефолт із кодового рядка (як це був випадок із DATABASE_URL)."""
    secret_keys = set(_load(SECRET).get("stringData") or {})
    required = {"POSTGRES_PASSWORD", "JWT_SECRET", *SECRET_ONLY_KEYS}
    assert required <= secret_keys, f"у secret.yaml немає: {sorted(required - secret_keys)}"


def test_placeholder_secrets_are_marked_as_not_for_production() -> None:
    # Значення в репозиторії — заглушки. Якщо хтось їх замінить на справжні
    # секрети, нотатка зникне разом із єдиним сигналом про це.
    header = "\n".join(SECRET.read_text(encoding="utf-8").splitlines()[:6])
    assert "НЕ для продакшену" in header


def _all_service_docs() -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for path in sorted(BASE.glob("*.yaml")):
        for doc in _documents(path):
            if doc.get("kind") == "Service":
                out.append((path.name, doc))
    return out


def test_services_with_nodeport_declare_the_nodeport_type() -> None:
    """nodePort можливий лише для type: NodePort.

    Регресія, знайдена на kind-E2E: у jaeger.yaml був nodePort: 30086 без
    `type: NodePort`, тож Service лишався ClusterIP, а apiserver відхиляв
    увесь apply — разом із усіма іншими ресурсами маніфесту. `kubectl
    kustomize` такий Service пропускає: він перевіряє синтаксис, а не
    семантику API.
    """
    offenders = {
        f"{filename}/{doc['metadata']['name']}": port.get("nodePort")
        for filename, doc in _all_service_docs()
        for port in (doc.get("spec", {}).get("ports") or [])
        if port.get("nodePort") is not None and doc.get("spec", {}).get("type") != "NodePort"
    }
    assert offenders == {}, f"nodePort без type: NodePort: {offenders}"


def test_configmap_keys_have_no_slashes() -> None:
    """Ключ ConfigMap не може містити "/" (regex [-._a-zA-Z0-9]+).

    Kustomize це дозволяє, тож помилка вилізає лише на `kubectl apply`:
    grafana-provisioning з ключами "datasources/datasource.yaml" змусив
    відхилити весь маніфест. Розділення на підкаталоги робиться через
    subPath у volumeMounts, а не через "/" у ключі.
    """
    bad: dict[str, list[str]] = {}
    for path in sorted(BASE.glob("*.yaml")):
        for doc in _documents(path):
            if doc.get("kind") != "ConfigMap":
                continue
            keys = list(doc.get("data") or {}) + list(doc.get("binaryData") or {})
            invalid = [key for key in keys if "/" in key]
            if invalid:
                bad[f"{path.name}/{doc['metadata']['name']}"] = invalid
    assert bad == {}, f"ключі ConfigMap зі слешем: {bad}"


def test_generated_configmap_keys_have_no_slashes() -> None:
    """Те саме для configMapGenerator у kustomization.yaml.

    Тут інваріант не читається з YAML напряму: kustomize генерує ConfigMap
    під час збірки, тож перевіряємо його складальник — саме він раніше
    вписав ключі зі слешем.
    """
    kustomization = _load(BASE / "kustomization.yaml")
    bad: list[str] = []
    for entry in kustomization.get("configMapGenerator") or []:
        for item in entry.get("files") or []:
            key = str(item).split("=", 1)[0]
            if "/" in key:
                bad.append(f"{entry.get('name')}: {key}")
    assert bad == [], f"configMapGenerator з ключами зі слешем: {bad}"


def _app_env_of(overlay: Path | None) -> str | None:
    """APP_ENV, який отримає застосунок. Overlay з patch'ем читаємо вручну:
    kustomize в тестах не запускаємо, а розбіжність між base і overlay
    тут і була причиною падіння migrations на kind."""
    if overlay is None:
        return _load(CONFIGMAP)["data"]["APP_ENV"]
    kustomization = _load(overlay / "kustomization.yaml")
    for patch in kustomization.get("patches") or []:
        body = patch.get("patch") or ""
        if "APP_ENV" in body and (patch.get("target") or {}).get("name") == "cyberops-config":
            match = re.search(r"value:\s*(\S+)", body)
            if match:
                return match.group(1).strip("'\"")
    return _load(CONFIGMAP)["data"]["APP_ENV"]


def test_dev_overlay_runs_as_dev_with_the_placeholder_secrets() -> None:
    """Стенд (і kind-E2E) працює на заглушках із base/secret.yaml.

    Якщо overlay лишає APP_ENV=prod, охорона з app/config.py (яка тепер
    перевіряє і "prod", див. test_jwt_secret.py) відмовиться стартувати, і
    Job migrations впаде в ValidationError. Тому dev-стенд мусить бути dev.
    """
    assert _app_env_of(OVERLAYS / "dev") == "dev"


def test_base_manifests_stay_in_production_mode() -> None:
    """Base — це основа для прод-оверлея, тож APP_ENV=prod. Якщо змінити на
    dev, охорона не спрацює ніде: реальні деплої беруть саме base."""
    assert _app_env_of(None) == "prod"
