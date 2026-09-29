"""Інваріанти k8s-манифестів: хто має доступ до Secret, а що — ні.

Натхнення — `test_compose_exposure.py`: CI перевіряє лише `kubectl kustomize`,
тобто синтаксис. Регресія, яку вона не бачить: ключ перенесли з ConfigMap у
Secret, а якийсь контейнер забув підключити Secret — маніфест лишається
валідним, Job падає вже на стенді. Саме так v1.12 зламав `migrations`:
`DATABASE_URL` переїхав у Secret, а Job мав лише `configMapRef`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML приходить з uvicorn[standard]")

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "infrastructure" / "kubernetes" / "base"
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
