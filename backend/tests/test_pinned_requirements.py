"""Сторожі на піни залежностей: `==X.Y.*` не ламає збірку, а тихо розмикає її.

`==0.141.*` — валідний PEP 440, тож pip не скаржиться, CI зелений, а образ
невідтворюваний: наступний `pip install -r` міг зняти 0.141.2. Зібрані два
файли цього проєкту майже повністю складалися з таких записів (один `bcrypt`
був точним із 29), тож «у нас пінований стек» було неправдою.

Другий сторож — пін має називати те, на чому реальноRUNять тести. Розбіжність
непомітна: requirements розходиться з оточенням, тести зелені на старому, а
прод збирається на новому. Таке вже було з `websockets` (12.0 у gateway, 17.1
в оточенні), тож перевірка потрібна не тільки на синтаксис.
"""

from __future__ import annotations

import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent

# (шлях, чи імпортується під час тестів) — gateway не встановлюється в CI
# окремо, але його тести живуть у backend (pythonpath містить `..`), тож
# залежності gateway мають бути встановлені там.
REQUIREMENT_FILES = (
    APP_ROOT / "requirements.txt",
    APP_ROOT.parent / "gateway" / "requirements.txt",
)

# `name[extras]==1.2.3` — рівний пін. Версія не обов'язково з трьох чисел:
# opentelemetry `-інструментації` мають пререлізні зрізи (`0.66b0`), тож
# заборонено лише `.*` (розмитість), а не «три числа».
PINNED = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]+\])?==([A-Za-z0-9][A-Za-z0-9.!+_-]*)$")
WILDCARD = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]+\])?==(.+)$")


def _requirements() -> dict[Path, list[str]]:
    result: dict[Path, list[str]] = {}
    for path in REQUIREMENT_FILES:
        lines = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.split("#", 1)[0].strip()
            if line:
                lines.append(line)
        result[path] = lines
    return result


def test_requirements_files_exist() -> None:
    """Файли, які сторож перевіряє, мають бути на місці.

    Інакше наступна перевірка мовчки перевірить порожнечу: якщо шлях
    перейменували, `rglob`/`read_text` не знайдуть нічого й тест стане зеленим
    на відсутності правил.
    """
    missing = [str(path) for path in REQUIREMENT_FILES if not path.is_file()]
    assert not missing, f"Немає файлів залежностей: {'; '.join(missing)}"


def test_no_wildcard_pins() -> None:
    """Жодна пряма залежність не має закінчуватися на `.*`."""
    offenders: list[str] = []
    for path, lines in _requirements().items():
        for line in lines:
            if WILDCARD.fullmatch(line) and not PINNED.fullmatch(line):
                offenders.append(f"{path.name}: {line}")

    assert not offenders, (
        "Дивні піни — `==X.Y.*` фіксує лише мажорну й мінорну частину, тому образ "
        "не відтворюється. Потрібен рівний пін (напр. `==1.2.3`): " + "; ".join(offenders)
    )


def test_every_requirement_is_pinned_exactly() -> None:
    """Кожен рядок — це `==` із рівною версією, без діапазонів і без extras-only."""
    offenders: list[str] = []
    for path, lines in _requirements().items():
        for line in lines:
            if not PINNED.fullmatch(line):
                offenders.append(f"{path.name}: {line}")

    assert not offenders, (
        "Очікується рівний пін виду `пакет[extras]==X.Y.Z`: " + "; ".join(offenders)
    )


def test_pins_match_installed_versions() -> None:
    """Пін у файлі має називати ту версію, на якій щойно прогналися тести.

    `pip-audit` і CI цього не ловлять: вони перевіряють безпеку, а не
    відповідність файлу оточенню. Розбіжність означає, що тести зелені на
    одній версії, а образ збирається з іншої — тобто «зелено» не означає
    «перевірено».
    """
    mismatches: list[str] = []
    for path, lines in _requirements().items():
        for line in lines:
            match = PINNED.fullmatch(line)
            if match is None:
                continue
            name, _extras, pin = match.groups()
            try:
                installed = version(name)
            except PackageNotFoundError:
                mismatches.append(f"{path.name}: {name} — пін {pin}, не встановлено")
                continue
            if installed != pin:
                mismatches.append(f"{path.name}: {name} — пін {pin}, встановлено {installed}")

    assert not mismatches, (
        "Піни розійшлися з оточенням, у якому проходять тести: "
        + "; ".join(mismatches)
        + ". Виправте або оновіть оточення до пінованих версій."
    )


def test_gateway_dependencies_are_testable_from_backend() -> None:
    """Тести імпортують `gateway.main`, тож його залежності мають бути в backend.

    `conftest.py` імпортує `gateway.main` (через `pythonpath = . ..` у
    `pytest.ini`), а `gateway/main.py` імпортує `websockets` для релеї `/ws`.
    Спеціального `gateway/requirements.txt` у тестовому оточенні немає — отже,
    якщо залежність gateway не продубльована в `backend/requirements.txt`, тести
    тримаються на транзитивному завантаженні й падають від того, що візьме
    `uvicorn[standard]`, а не від зміни в цьому репозиторії.
    """
    backend_pins = {
        PINNED.fullmatch(line).group(1).lower()
        for line in _requirements()[APP_ROOT / "requirements.txt"]
        if PINNED.fullmatch(line)
    }

    gateway_pins = {
        PINNED.fullmatch(line).group(1).lower()
        for line in _requirements()[APP_ROOT.parent / "gateway" / "requirements.txt"]
        if PINNED.fullmatch(line)
    }

    missing = sorted(gateway_pins - backend_pins)
    assert not missing, (
        "Ці залежності потрібні тестам (через `import gateway.main`), але їх немає в "
        f"backend/requirements.txt: {', '.join(missing)}. Додай із тим самим значенням, "
        "що в gateway/requirements.txt."
    )
