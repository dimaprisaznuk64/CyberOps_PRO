"""Сторожі на застарілі символи: вони не ламають код, а тихо попереджають."""

from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent

# (символ, чим замінено) — обидва належать Starlette; старий псевдонім і далі
# існує, тож компілятор не допоможе: симптомом є лише warning у тестах, який
# легко не помітити. Тому шукаємо його прямо в коді.
BANNED = {
    "HTTP_422_UNPROCESSABLE_ENTITY": "HTTP_422_UNPROCESSABLE_CONTENT",
}


def _source_files() -> list[Path]:
    roots = [APP_ROOT / "app", APP_ROOT.parent / "gateway", APP_ROOT.parent / "workers"]
    files: list[Path] = []
    for root in roots:
        files.extend(sorted(root.rglob("*.py")))
    return files


def test_no_banned_starlette_aliases_in_source() -> None:
    """Жоден застарілий аліас Starlette не залишився в коді застосунку."""
    offenders: list[str] = []
    for path in _source_files():
        text = path.read_text(encoding="utf-8")
        for banned, replacement in BANNED.items():
            if banned not in text:
                continue
            for line in text.splitlines():
                if banned in line and replacement not in line:
                    offenders.append(f"{path.name}:{line.strip()}")
                    break

    assert not offenders, (
        f"Застарілі аліаси Starlette у коді (замініть на: {', '.join(set(BANNED.values()))}): "
        + "; ".join(offenders)
    )