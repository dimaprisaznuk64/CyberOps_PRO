from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from app.config import settings
from app.models.finding import Finding
from app.services.logging_config import get_logger

logger = get_logger("app.ai")

SEVERITY_SCORE = {"critical": 10, "high": 7, "medium": 3, "low": 1, "info": 0}

_IMPACT_BY_SEVERITY = {
    "info": "Інформаційна знахідка: порт/сервіс виявлено, але суттєвого ризику не зафіксовано.",
    "low": "Низький ризик: проблема локальна, для експлуатації потрібен доступ або певні умови.",
    "medium": (
        "Середній ризик: проблема може бути використана навмисно чи випадково "
        "й завдати помірної шкоди."
    ),
    "high": "Високий ризик: проблема легко експлуатується та може скомпрометувати сервіс або дані.",
    "critical": "Критичний ризик: проблема з високою ймовірністю призведе до повної компрометації.",
}

_REMEDIATION_BY_SEVERITY = {
    "info": "Спостерігати за сервісом; переконатися, що порт закритий ззовні.",
    "low": "Оновити сервіс, закрити порт файрволом, якщо він не потрібен ззовні.",
    "medium": (
        "Закрити порт з публічного доступу, оновити версію, налаштувати "
        "автентифікацію та обмеження доступу."
    ),
    "high": (
        "Негайно закрити порт/сервіс, оновити або замінити на захищену версію, "
        "додати додатковий захист."
    ),
    "critical": (
        "Негайно ізолювати сервіс, закрити доступ, усунути вразливість "
        "і провести розслідування інциденту."
    ),
}

_SYSTEM_PROMPT = (
    "Ти — AI security-асистент платформи CyberOps PRO. "
    "Пояснюєш знахідки сканування. Відповідай ТІЛЬКИ валідним JSON без markdown, "
    'ключі: "explanation", "impact", "risk_explanation", "remediation". '
    "Мова відповіді — українська. "
    "explanation: що знайдено та чому це вразливість; "
    "impact: який вплив на систему/дані; "
    "risk_explanation: що означає рівень ризику (навчальний score 0/1/3/7/10) для цієї знахідки; "
    "remediation: конкретні кроки як виправити."
)


@dataclass
class AIExplanation:
    provider: str
    explanation: str
    impact: str
    risk_explanation: str
    remediation: str


def _api_provider() -> str:
    provider = (settings.ai_provider or "").strip().lower()
    if provider in ("ollama", "openai", "openai-compatible", "compatible", "api"):
        return provider
    return ""


def _finding_context(finding: Finding) -> dict[str, object]:
    svc = finding.service
    return {
        "title": finding.title,
        "severity": finding.severity,
        "risk_score": SEVERITY_SCORE.get(finding.severity.lower(), 0),
        "description": finding.description or "",
        "cve": finding.cve,
        "service": (
            {
                "port": svc.port,
                "protocol": svc.protocol,
                "service": svc.service,
                "product": svc.product or "",
                "version": svc.version or "",
            }
            if svc is not None
            else None
        ),
    }


def _build_prompt(finding: Finding) -> str:
    ctx = json.dumps(_finding_context(finding), ensure_ascii=False)
    return (
        "Контекст знахідки (JSON):\n"
        f"{ctx}\n"
        "Поверни JSON з ключами explanation, impact, risk_explanation, remediation."
    )


def _chat_endpoint() -> str:
    return settings.ai_base_url.rstrip("/") + "/chat/completions"


def _parse_json_content(content: str) -> dict[str, str] | None:
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            data = json.loads(content[start : end + 1])
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    keys = ("explanation", "impact", "risk_explanation", "remediation")
    return {k: str(data[k]) for k in keys if k in data}


def _from_dict(provider: str, data: dict[str, str]) -> AIExplanation | None:
    try:
        return AIExplanation(
            provider=provider,
            explanation=data["explanation"],
            impact=data["impact"],
            risk_explanation=data["risk_explanation"],
            remediation=data["remediation"],
        )
    except KeyError:
        return None


def _rule_based(finding: Finding) -> AIExplanation:
    ctx = _finding_context(finding)
    svc = ctx["service"]
    if svc:
        base = f"{svc['service']} на порту {svc['port']}/{svc['protocol']}"
        if svc["product"] or svc["version"]:
            base += f" ({svc['product']} {svc['version']})".strip()
        explanation = f"Виявлено: {ctx['title']}. Сервіс {base} доступний і може бути атакований."
    else:
        extra = ctx["description"]
        base_msg = f"Виявлено: {ctx['title']}."
        explanation = f"{base_msg} {extra}" if extra else base_msg
    severity = ctx["severity"].lower()
    score = ctx["risk_score"]
    impact = _IMPACT_BY_SEVERITY.get(severity, _IMPACT_BY_SEVERITY["info"])
    risk_explanation = (
        f"Рівень ризику — {severity.upper()} (навчальний score {score} з 10: "
        "info=0, low=1, medium=3, high=7, critical=10). "
        "Чим вищий score, тим більша ймовірність і масштаб шкоди."
    )
    remediation = finding.recommendation or _REMEDIATION_BY_SEVERITY.get(severity, "")
    return AIExplanation("rule", explanation, impact, risk_explanation, remediation)


async def explain_finding(finding: Finding) -> AIExplanation:
    provider = _api_provider()
    if provider:
        try:
            headers = {}
            if settings.ai_api_key:
                headers["Authorization"] = f"Bearer {settings.ai_api_key}"
            async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds) as client:
                resp = await client.post(
                    _chat_endpoint(),
                    headers=headers,
                    json={
                        "model": settings.ai_model,
                        "messages": [
                            {"role": "system", "content": _SYSTEM_PROMPT},
                            {"role": "user", "content": _build_prompt(finding)},
                        ],
                        "temperature": 0.2,
                    },
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
            parsed = _parse_json_content(content)
            if parsed is not None:
                result = _from_dict(f"api/{settings.ai_model}", parsed)
                if result is not None:
                    return result
            logger.warning("ai_unparseable_response", extra={"model": settings.ai_model})
        except Exception as exc:
            logger.warning("ai_provider_error", extra={"provider": provider, "error": str(exc)})
    return _rule_based(finding)