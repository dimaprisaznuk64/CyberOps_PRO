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



WORKFLOWS = ROOT / ".github" / "workflows"
SMOKE_SCRIPT = ROOT / "scripts" / "smoke.sh"


@pytest.mark.parametrize("workflow", ["deploy.yml", "prod-e2e.yml"])
def test_both_stands_use_the_same_smoke_script(workflow: str) -> None:
    """Перевірки поведінки мають бути одні й ті самі на обох стендах.

    Копія smoke-тесту в двох воркфлоу розходиться з першою ж правкою: щось
    додали в одному стенді й забули в іншому, а далі «CI зелений» більше
    нічого не означає. Спільний скрипт робить розходження неможливим
    навіть без цього тесту.
    """
    text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
    assert "scripts/smoke.sh" in text, f"{workflow} не використовує спільний smoke.sh"


def test_smoke_script_checks_behaviour_not_just_liveness() -> None:
    """Скрипт має доводити можливість скористатися, а не лише що порт відповідає.

    Регресія попереднього стану: один `curl /health` був зелений тричі поспіль
    на системі, у якій ніхто не міг увійти.
    """
    text = SMOKE_SCRIPT.read_text(encoding="utf-8")
    for needle in (
        "/health",
        "/runtime-config.js",
        "api/v1/auth/login",
        "api/v1/assets",
        "Origin:",
    ):
        assert needle in text, f"у smoke.sh немає перевірки {needle}"
    # Значення, з якими порівнюємо, приходять ззовні: з ConfigMap чи з
    # compose env. Константа в самому скрипті означала б, що тест
    # підтверджує себе сам.
    assert "EXPECTED_API_URL" in text


def test_ci_does_not_bake_the_api_url_into_published_images() -> None:
    """Опублікований образ не має бути прив'язаний до адреси збірки.

    Регресія: `docker.yml` збирав frontend із
    `build-args: NEXT_PUBLIC_API_URL=http://localhost:8000`, тож кожен, хто
    візьме образ з GHCR, отримає UI, який ходить у localhost СВОГО
    браузера. Локально це непомітно — важливо, що саме образ у реєстрі.
    """
    docker_workflow = (WORKFLOWS / "docker.yml").read_text(encoding="utf-8")
    # Коментарі не враховуємо: пояснення, чому аргумент прибрано, закономірно
    # згадує його назву, і тест падав би через власний коментар.
    code = "\n".join(
        line for line in docker_workflow.splitlines() if not line.lstrip().startswith("#")
    )
    assert "NEXT_PUBLIC_API_URL" not in code, (
        "CI знову вписує адресу API в опублікований образ — образ стане "
        "прив'язаним до адреси, під якою його зібрали"
    )


# --- v1.16: спостережуваність, яку ніхто не перевіряв ------------------------
#
# До v1.16 весь observability-стек був увімкнений «на очі»: Jaeger, Prometheus і
# Grafana піднімалися на обох стендах, але жодна перевірка не дивилася, чи вони
# бачать те, що їм доручено. Наслідок — баг, який жив у конфігурації роками й
# був невидимий: Prometheus скрейпив jaeger:14269, а k8s Service цей порт не
# експортував. `kubectl kustomize` такий конфіг приймає, compose так само, а
# дашборд просто має порожню панель — виглядає як «немає трафіку».

PROMETHEUS_LOCAL = ROOT / "monitoring" / "prometheus.yml"
PROMETHEUS_MANIFEST = BASE / "prometheus.yaml"


def _prometheus_scrape_config() -> dict[str, Any]:
    """Конфіг, який згодом побачить Prometheus на стенді.

    Беремо з ConfigMap у prometheus.yaml, а не з monitoring/prometheus.yml:
    перевіряємо саме те, що застосується в k8s.
    """
    for doc in _documents(PROMETHEUS_MANIFEST):
        if doc.get("kind") == "ConfigMap":
            raw = (doc.get("data") or {}).get("prometheus.yml")
            assert raw, "у prometheus.yaml немає ключа prometheus.yml"
            return yaml.safe_load(raw)
    raise AssertionError("ConfigMap із prometheus.yml не знайдено")


def _service_ports() -> dict[str, set[int]]:
    """Service -> множина портів, які він реально експортує.

    Prometheus ходить на Service-адресу, а не на Pod IP, тож неоголошений порт
    недоступний, навіть якщо контейнер його слухає.
    """
    ports: dict[str, set[int]] = {}
    for _filename, doc in _all_service_docs():
        name = doc["metadata"]["name"]
        ports.setdefault(name, set()).update(
            port["port"] for port in doc.get("spec", {}).get("ports") or []
        )
    return ports


def test_every_prometheus_target_is_backed_by_a_service_port() -> None:
    """Головний інваріант v1.16: таргет скрейпу мусить мати Service, який
    експортує саме цей порт.

    Регресія: `cyberops-jaeger -> jaeger:14269`, де 14269 — admin-порт Jaeger
    (`/metrics`, згідно документації all-in-one). Але Service `jaeger` мав
    лише 4318 і 16686, тож Prometheus скрейпив порт, якого в Service немає, і
    таргет лишався DOWN. Ніхто цього не бачив: статус таргетів не читав ніхто.
    """
    services = _service_ports()
    broken: dict[str, str] = {}
    for job in _prometheus_scrape_config().get("scrape_configs") or []:
        for static in job.get("static_configs") or []:
            for target in static.get("targets") or []:
                host, _, port = target.rpartition(":")
                if host in {"localhost", "127.0.0.1"}:
                    # self-скрейп: Prometheus скрейпить сам себе всередині
                    # контейнера, Service для цього не потрібен.
                    continue
                if host not in services:
                    broken[target] = f"немає Service {host!r}"
                elif int(port) not in services[host]:
                    broken[target] = (
                        f"Service {host!r} експортує {sorted(services[host])}, "
                        f"а таргет просить {port}"
                    )
    assert broken == {}, f"тарагети Prometheus без Service: {broken}"


def test_both_stands_ship_the_same_prometheus_config() -> None:
    """Конфіг Prometheus не має існувати у двох незалежних копіях.

    compose монтує monitoring/prometheus.yml, а k8s ConfigMap містить його
    копію. Kustomize не дає посилатися на файл поза своїм каталогом, тому
    джерелом істини лишається файл, а цей тест не дає копії розійтися з ним.
    """
    embedded = _prometheus_scrape_config()
    local = yaml.safe_load(PROMETHEUS_LOCAL.read_text(encoding="utf-8"))
    assert embedded == local, (
        "monitoring/prometheus.yml розійшовся з копією в prometheus.yaml — "
        "Prometheus на compose і в k8s скрейпитимуть різні набори таргетів"
    )


def test_grafana_password_is_not_hardcoded_in_the_manifest() -> None:
    """Grafana не має брати пароль із літерала в YAML.

    Регресія: `GF_SECURITY_ADMIN_PASSWORD: admin` прямо в grafana.yaml, при
    тому що compose-prod вимагав обов'язковий GRAFANA_ADMIN_PASSWORD. Service
    виставлений назовні (nodePort 30300), тож публічний інстанс мав admin/admin
    — рівно той самий клас діри, що APP_ENV="production" vs "prod" у v1.13:
    захист був у compose-шляху й мертвий у k8s-шляху.
    """
    grafana = _find_workload(BASE / "grafana.yaml", "grafana")
    env = {entry["name"]: entry for entry in _containers(grafana)[0].get("env") or []}
    password = env.get("GF_SECURITY_ADMIN_PASSWORD")
    assert password is not None, "grafana без GF_SECURITY_ADMIN_PASSWORD"
    assert "value" not in password, (
        f"пароль Grafana захардкожено: {password['value']!r} — "
        "він мусить приходити зі Secret"
    )
    ref = (password.get("valueFrom") or {}).get("secretKeyRef") or {}
    assert ref.get("name") and ref.get("key"), (
        "пароль Grafana має приходити через secretKeyRef"
    )
    secret_keys = _load(SECRET).get("stringData") or {}
    assert ref["key"] in secret_keys, (
        f"ключа {ref['key']!r} немає в secret.yaml — контейнер впав би з "
        "CreateContainerConfigError"
    )


def test_deploy_waits_for_every_deployment_it_applies() -> None:
    """E2E мусить чекати на кожен застосований Deployment.

    Регресія: цикл `for d in ...` у deploy.yml містив 10 імен, а в base було
    11 деплойментів — `jaeger` був пропущений. Тобто міг не піднятися
    колектор, до якого йдуть OTLP-спани з усіх сервісів, а E2E був зелений.
    Список у воркфлоу не оновлюється разом із маніфестами, тож міг
    розійтися знову; тепер він береться з кластера.
    """
    workflow = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    code = "\n".join(
        line for line in workflow.splitlines() if not line.lstrip().startswith("#")
    )
    assert "get deployments" in code, (
        "deploy.yml має брати список деплойментів із кластера, а не з константи"
    )
    assert not re.search(r"for d in (?!\$\()\w", code), (
        "у deploy.yml знову з'явився перелік деплойментів літералом — він "
        "розійдеться з маніфестами при першій же зміні"
    )


def test_smoke_script_checks_observability_not_just_the_app() -> None:
    """Стенд мусить доводити, що моніторинг бачить систему, а не лише що
    бекенд відповідає.

    До v1.16 smoke.sh перевіряв `/health`, UI, CORS і вхід — усе про застосунок.
    Жодної перевірки не було про Prometheus, Jaeger і Grafana, тож стенд із
    мертвим моніторингом проходив E2E. Імена сервісів приходять ззовні:
    константа всередині означала б, що тест підтверджує себе сам.
    """
    text = SMOKE_SCRIPT.read_text(encoding="utf-8")
    for needle in (
        "PROMETHEUS_URL",
        "/api/v1/targets",
        "JAEGER_URL",
        "/api/services",
        "/api/traces",
        "GRAFANA_URL",
        "/api/datasources",
        "/health",
    ):
        assert needle in text, f"у smoke.sh немає перевірки {needle}"
    assert "EXPECTED_TRACE_SERVICES" in text


@pytest.mark.parametrize("workflow", ["deploy.yml", "prod-e2e.yml"])
def test_both_stands_point_the_smoke_test_at_their_observability_stack(
    workflow: str,
) -> None:
    """Обидва стенди мусять передавати ті самі адреси спостережуваності.

    Інакше стенди знову розійдуться: один перевіряє моніторинг, другий — ні,
    і «CI зелений» перестане щось означати (те саме, що зі скопійованим
    smoke-тестом у v1.15).
    """
    text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
    for needle in (
        "PROMETHEUS_URL",
        "JAEGER_URL",
        "GRAFANA_URL",
        "GRAFANA_PASS",
        "EXPECTED_TRACE_SERVICES",
    ):
        assert needle in text, f"{workflow} не передає {needle} у smoke.sh"
    # kind має ще й пробросить порти: там спостережуваність не на localhost.
    if workflow == "deploy.yml":
        for service in ("prometheus", "jaeger", "grafana"):
            assert f"svc/{service}" in text, f"deploy.yml не робить port-forward для {service}"

