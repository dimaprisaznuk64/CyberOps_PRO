"""Інваріанти k8s-манифестів: хто має доступ до Secret, а що — ні.

Натхнення — `test_compose_exposure.py`: CI перевіряє лише `kubectl kustomize`,
тобто синтаксис. Регресія, яку вона не бачить: ключ перенесли з ConfigMap у
Secret, а якийсь контейнер забув підключити Secret — маніфест лишається
валідним, Job падає вже на стенді. Саме так v1.12 зламав `migrations`:
`DATABASE_URL` переїхав у Secret, а Job мав лише `configMapRef`.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
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


def _injected_service_env_names() -> dict[str, str]:
    """Змінні, які kubelet підставляє в контейнери сам, без нашої волі.

    Для кожного Service(namespace) створюються `<SERVICE>_SERVICE_HOST` і
    `<SERVICE>_SERVICE_PORT`, а для кожного порту — `<SERVICE>_<PORTNAME>`,
    де для безіменного порту PORTNAME = `PORT`. Значення — рядок
    `tcp://<ClusterIP>:<port>`, а не число.

    Регресія з kind-E2E: Service `gateway` має безіменний порт, тож kubelet
    підставляв `GATEWAY_PORT=tcp://10.96.49.219:8000` — рівно те ім'я, яке
    entrypoint.sh читав як номер порту. Uvicorn отримував не число і падав у
    CrashLoopBackOff. Тест нижче фіксує саме цю колізію, бо вона не видима
    ні в YAML, ні в kustomize: змінної з таким значенням у маніфестах немає.
    """
    names: dict[str, str] = {}
    for filename, doc in _all_service_docs():
        service = doc["metadata"]["name"].upper().replace("-", "_")
        for port in doc.get("spec", {}).get("ports") or []:
            suffix = str(port.get("name") or "PORT").upper().replace("-", "_")
            names[f"{service}_{suffix}"] = f"{filename}: {doc['metadata']['name']}"
    return names


def _env_from_config() -> set[str]:
    """Імена змінних, які код читає з оточення із власним дефолтом.

    Такі змінні не приходять із ConfigMap/Secret, тож єдине, що може
    підставити їм значення, — сам kubelet. Тому саме вони й дістають
    колізію з іменами Service; ключі, ями явно є в маніфестах, приходять
    із pod spec і мають пріоритет, тож їх не перевіряємо.
    """
    entrypoint = (ROOT / "gateway" / "entrypoint.sh").read_text(encoding="utf-8")
    names = set(re.findall(r"\$\{([A-Z0-9_]+):-", entrypoint))
    names |= {name.upper() for name in _settings_fields()}
    declared = set(_load(CONFIGMAP).get("data") or {}) | set(
        _load(SECRET).get("stringData") or {}
    )
    return {name for name in names if name not in declared}


def _settings_fields() -> set[str]:
    """Поля конфігів з власними дефолтами (gateway і backend).

    Джерело істини — самі моделі, а не regex по коду: перейменування поля
    змінює ім'я змінної, і тест має йти за ним автоматично.
    """
    fields: set[str] = set()
    try:
        from app.config import Settings

        from gateway.config import GatewaySettings
    except Exception:  # pragma: no cover - импорти недоступні поза тестовим оточенням
        return fields
    fields |= set(Settings.model_fields) | set(GatewaySettings.model_fields)
    return fields


def test_app_env_defaults_do_not_collide_with_injected_service_env() -> None:
    """Код не має читати змінну з тим самим іменем, яке kubelet підставляє
    для Service: інакше підміняється несподіваним `tcp://<ip>:<port>`."""
    injected = _injected_service_env_names()
    # Точність самого інваріанта: без цього assert тест був би зелений
    # навіть якби ми перестали генерувати імена Service.
    assert "GATEWAY_PORT" in injected, "очікувана колізія зникла — інваріант не діє"
    clashes = {
        name: injected[name] for name in _env_from_config() if name in injected
    }
    assert clashes == {}, f"ім'я змінної з коду збігається з іменем Service: {clashes}"


def test_declared_env_names_do_not_collide_with_injected_service_env() -> None:
    """Те саме, але для змінних, які ми задаємо МИТНО — у ConfigMap, Secret
    або в pod env.

    Такі випадки не ламають застосунок (pod spec має пріоритет над змінними
    Service), але роблять значенням неоднозначним: людина читає маніфест, бачить
    `GATEWAY_PORT` у ConfigMap і не здогадується, що колись це було не те
    значення. Тому забороняємо колізію навіть там, де вона безпечна.
    """
    injected = _injected_service_env_names()
    declared: dict[str, str] = {}
    configmap = _load(CONFIGMAP).get("data") or {}
    secret = _load(SECRET).get("stringData") or {}
    for key in (*configmap, *secret):
        declared.setdefault(key, "configmap.yaml/secret.yaml")
    for path in sorted(BASE.glob("*.yaml")):
        for doc in _documents(path):
            spec = doc.get("spec", {})
            template = spec.get("template", spec)
            for container in (template.get("spec") or {}).get("containers") or []:
                for entry in container.get("env") or []:
                    if "name" in entry:
                        declared.setdefault(str(entry["name"]), f"{path.name}")
    clashes = {name: declared[name] for name in declared if name in injected}
    assert clashes == {}, f"оголошена змінна має таке саме ім'я, як у Service: {clashes}"


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


# Образи, які збираємо самі (docker compose build -> kind load). Їх немає в
# жодному registry, тож kubelet не має намагатися їх тягнути.
LOCAL_IMAGES = (
    "cyberops/cyberops-backend",
    "cyberops/cyberops-worker",
    "cyberops/cyberops-gateway",
    "cyberops/cyberops-frontend",
)


def _image_of(container: dict[str, Any]) -> str:
    return str(container.get("image", "")).split(":", 1)[0]


def _is_local_image(image: str) -> bool:
    return any(image.startswith(prefix) for prefix in LOCAL_IMAGES)


def test_local_images_are_not_pulled_by_default() -> None:
    """Регресія з kind-E2E: frontend був у ImagePullBackOff.

    Образ `cyberops/cyberops-frontend` записаний без тега, тобто це `:latest`.
    Для `:latest` kubelet за замовчуванням ставить `imagePullPolicy: Always` і
    йде в registry за образом, якого там немає. Решта наших деплойів мали
    `IfNotPresent` явно, тож падав лише frontend — і `kubectl kustomize` це
    пропускає: pull-policy він не перевіряє взагалі.
    """
    offenders: dict[str, Any] = {}
    for path in sorted(BASE.glob("*.yaml")):
        for doc in _documents(path):
            spec = doc.get("spec", {})
            template = spec.get("template", spec)
            for kind in ("containers", "initContainers"):
                for container in (template.get("spec") or {}).get(kind) or []:
                    image = _image_of(container)
                    policy = container.get("imagePullPolicy")
                    if _is_local_image(image) and policy != "IfNotPresent":
                        offenders[f"{path.name}/{doc['metadata']['name']}/{kind}"] = image
    assert offenders == {}, f"свої образи без imagePullPolicy: IfNotPresent: {offenders}"


def test_gateway_liveness_does_not_depend_on_upstreams() -> None:
    """LivenessProbe не має вимірювати здоров'я залежностей.

    Регресія з kind-E2E: gateway падав у CrashLoopBackOff. Його `/health`
    перевіряє ще й core/auth і повертає 503, коли вони не готові — правильно
    для readiness, але не для liveness: kubelet убиває здоровий проксі, бо
    внизу не відповідають. Liveness дивиться лише на себе (`/health/live`).
    """
    gateway = _find_workload(BASE / "gateway.yaml", "gateway")
    containers = _containers(gateway)
    assert containers, "gateway без контейнерів"
    container = containers[0]
    liveness = ((container.get("livenessProbe") or {}).get("httpGet") or {}).get("path")
    readiness = ((container.get("readinessProbe") or {}).get("httpGet") or {}).get("path")
    assert liveness, "у gateway немає livenessProbe"
    assert liveness != "/health", (
        "livenessProbe на /health зробить gateway залежним від core/auth: "
        "їхня недоступність перезапускатиме проксі (див. /health/live)"
    )
    assert readiness == "/health", "readinessProbe має лишатись на агрегованому /health"
    # Шлях livenessProbe мусить бути реальним маршрутом: інакше probe дістає
    # 404 і kubelet перезапускає контейнер нескінченно — знову CrashLoop, уже
    # з іншої причини, яку тест вище не побачить.
    source = (ROOT / "gateway" / "main.py").read_text(encoding="utf-8")
    assert f'get("{liveness}")' in source, f"маршруту {liveness} немає в gateway/main.py"


def test_migrations_wait_for_the_database_before_migrating() -> None:
    """Job міграцій мусить дочекатися postgres, а не витрачати на це retry.

    Регресія з kind-E2E: Job падав двічі на connection refused і succeeds на
    третій спробі — backoffLimit: 3 витрачено майже весь. На повільнішому
    CI четвертої спроби не було б, і пайплайн зупинився б на таймауті
    "Wait migrations" без зрозумілої помилки. InitContainer чекає на БД, тож
    перша спроба — робоча.
    """
    migrations = _find_workload(BASE / "migrations.yaml", "migrations")
    spec = migrations.get("spec", {}).get("template", {}).get("spec", {})
    init_containers = spec.get("initContainers") or []
    assert init_containers, "у Job немає initContainer, який чекає на БД"
    waits = [c for c in init_containers if "postgres" in " ".join(map(str, c.get("command") or []))]
    assert waits, f"жоден initContainer не чекає на postgres: {init_containers}"
    # Чекати нема на що без DATABASE_URL — він у Secret.
    refs = [
        source["secretRef"]["name"]
        for container in init_containers
        for source in container.get("envFrom") or []
        if "secretRef" in source
    ]
    assert "cyberops-secrets" in refs, f"initContainer без Secret: {refs}"


def _wait_script() -> str:
    """Python із initContainer, який чекає на БД."""
    migrations = _find_workload(BASE / "migrations.yaml", "migrations")
    init_containers = migrations["spec"]["template"]["spec"].get("initContainers") or []
    for container in init_containers:
        command = [str(part) for part in container.get("command") or []]
        if "-c" in command:
            return command[command.index("-c") + 1]
    raise AssertionError("жоден initContainer не запускає python -c")


def _run_wait_script(database_url: str, timeout: str = "1") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", _wait_script()],
        env={**os.environ, "DATABASE_URL": database_url, "MIGRATIONS_WAIT_TIMEOUT": timeout},
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_migrations_wait_succeeds_once_the_database_accepts_connections() -> None:
    """Скрипт чекання має завершуватися 0, щоб Job перейшов до alembic."""
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        result = _run_wait_script(f"postgresql+asyncpg://u:p@127.0.0.1:{port}/cyberops")
    assert result.returncode == 0, f"чекання впало на готовій БД: {result.stderr}"
    assert "ready" in result.stdout


def test_migrations_wait_fails_loudly_when_the_database_is_absent() -> None:
    """Чекати вічно не можна: Job мусить впасти зрозумілим рядком, а не
    мовчки висити до backoffLimit."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        closed_port = probe.getsockname()[1]
    result = _run_wait_script(f"postgresql+asyncpg://u:p@127.0.0.1:{closed_port}/cyberops")
    assert result.returncode != 0, "чекання без БД мало б впасти"
    assert str(closed_port) in result.stderr, f"у помилці немає адреси БД: {result.stderr}"


def test_migrations_wait_understands_the_shipped_database_url() -> None:
    """Скрипт має розуміти той DATABASE_URL, який ми реально постачаємо.

    Розбір рядка — єдине місце, де тихо зламатись: якщо authority не
    витягнеться, скрипт не зможе підключитися й мовчки витратить увесь
    timeout на кожен деплой. Тому проганяємо його на значенні з secret.yaml.
    """
    database_url = (_load(SECRET).get("stringData") or {})["DATABASE_URL"]
    result = _run_wait_script(database_url)
    assert result.returncode != 0, "хост postgres має бути недоступним у тестах"
    assert "postgres:5432" in result.stderr, (
        f" authority не розпізнано з {database_url!r}: {result.stderr}"
    )


DEPLOY_WORKFLOW = ROOT / ".github" / "workflows" / "deploy.yml"


def test_smoke_test_verifies_login_not_only_health() -> None:
    """E2E має доводити, що в систему можна увійти, а не лише що вона відповідає.

    Регресія, знайдена на kind: усі поді були Running, `/health` був зелений,
    а адміністратора не існувало — сид падав на старті (міграції ще не
    накачені) і більше не повторювався. Старий smoke робив один `curl /health`
    і цю провину не бачив.

    Тому перевіряємо саме наявність кроку з логіном: його легко випадково
    видалити «на спрощення», і тоді CI знову стане зеленим на неробочій
    системі.
    """
    text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    assert "/api/v1/auth/login" in text, "у smoke-тесті немає перевірки логіну"
    assert "Authorization: Bearer" in text, " немає авторизованого запиту після нього"
    assert "::error::" in text, "кроки не вміють падати голосно"
