from __future__ import annotations

from typing import Any, TypedDict

from app.models.finding import (
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_INFO,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
)

RISK_WEIGHTS = {
    SEVERITY_INFO: 1,
    SEVERITY_LOW: 2,
    SEVERITY_MEDIUM: 4,
    SEVERITY_HIGH: 7,
    SEVERITY_CRITICAL: 10,
}

RISK_LEVEL_LOW = "LOW"
RISK_LEVEL_MEDIUM = "MEDIUM"
RISK_LEVEL_HIGH = "HIGH"
RISK_LEVEL_CRITICAL = "CRITICAL"


class FindingRule(TypedDict):
    severity: str
    title: str
    description: str
    recommendation: str
    cve: str | None


def _rule(
    severity: str,
    title: str,
    description: str,
    recommendation: str,
    cve: str | None = None,
) -> FindingRule:
    return {
        "severity": severity,
        "title": title,
        "description": description,
        "recommendation": recommendation,
        "cve": cve,
    }


RULE_BY_PORT: dict[int, FindingRule] = {
    21: _rule(
        SEVERITY_MEDIUM,
        "FTP без шифрування",
        "FTP передає логін і дані відкритим текстом.",
        "Замініть на SFTP/FTPS і ввімкніть явний (explicit) TLS.",
    ),
    23: _rule(
        SEVERITY_HIGH,
        "Telnet відкритий",
        "Telnet передає облікові дані без шифрування.",
        "Замініть telnet на SSH і заблокуйте порт 23.",
    ),
    512: _rule(
        SEVERITY_HIGH,
        "rlogin (rexec/exec) відкритий",
        "r-сервіси автентифікуються за довірою хоста без шифрування.",
        "Вимкніть r-сервіси, використовуйте SSH.",
    ),
    513: _rule(
        SEVERITY_HIGH,
        "rlogin (login) відкритий",
        "r-сервіси автентифікуються за довірою хоста без шифрування.",
        "Вимкніть r-сервіси, використовуйте SSH.",
    ),
    514: _rule(
        SEVERITY_HIGH,
        "rsh (shell) відкритий",
        "r-сервіси автентифікуються за довірою хоста без шифрування.",
        "Вимкніть r-сервіси, використовуйте SSH.",
    ),
    139: _rule(
        SEVERITY_MEDIUM,
        "NetBIOS/SMB виставлений",
        "SMB на 139 може бути мішенню експлойтів (EternalBlue тощо).",
        "Обмежте доступ файрволом, вимкніть SMBv1.",
    ),
    445: _rule(
        SEVERITY_MEDIUM,
        "SMB (microsoft-ds) виставлений",
        "SMB на 445 може бути мішенню експлойтів (EternalBlue тощо).",
        "Обмежте доступ файрволом, вимкніть SMBv1, застосуйте патчі.",
    ),
    1433: _rule(
        SEVERITY_HIGH,
        "Microsoft SQL Server виставлений",
        "MSSQL у публічній мережі — висока ймовірність брутфорсу.",
        "Обмежте доступ, використовуйте сильні паролі та шифрування.",
    ),
    1521: _rule(
        SEVERITY_HIGH,
        "Oracle DB виставлений",
        "Лістер Oracle у мережі ризиковий без налаштувань.",
        "Обмежте доступ і увімкніть шифрування мережі (TCPS).",
    ),
    3306: _rule(
        SEVERITY_MEDIUM,
        "MySQL виставлений",
        "MySQL відкритий у мережі — ризик брутфорсу.",
        "Обмежте доступ, використовуйте сильні паролі, HTTPS-тунелювання.",
    ),
    5432: _rule(
        SEVERITY_MEDIUM,
        "PostgreSQL виставлений",
        "PostgreSQL відкритий у мережі — ризик брутфорсу.",
        "Обмежте доступ pg_hba.conf і файрволом.",
    ),
    5900: _rule(
        SEVERITY_HIGH,
        "VNC виставлений",
        "VNC часто без пароля або зі слабким захистом.",
        "Використовуйте SSH-тунель і надійний пароль.",
    ),
    5985: _rule(
        SEVERITY_MEDIUM,
        "WinRM виставлений",
        "WinRM на 5985 може бути використаний для керування.",
        "Обмежте доступ і ввімкніть автентифікацію з підтвердженням.",
    ),
    5986: _rule(
        SEVERITY_MEDIUM,
        "WinRM (HTTPS) виставлений",
        "WinRM на 5986 може бути використаний для керування.",
        "Обмежте доступ і оновлюйте сертифікати.",
    ),
    623: _rule(
        SEVERITY_HIGH,
        "IPMI (RMCP+) виставлений",
        "IPMI може бути обійдений без автентифікації.",
        "Обмежте доступ до консолі керування (сервісний процесор).",
    ),
    11211: _rule(
        SEVERITY_MEDIUM,
        "Memcached виставлений",
        "Memcached може бути використаний для amplification-DDoS.",
        "Закрийте порт 11211 файрволом, змініть конфігурацію слухання.",
    ),
    27017: _rule(
        SEVERITY_HIGH,
        "MongoDB виставлений",
        "MongoDB часто без автентифікації — ризик витоку даних.",
        "Увімкніть авторизацію та обмежте доступ файрволом.",
    ),
    6379: _rule(
        SEVERITY_HIGH,
        "Redis виставлений",
        "Redis без пароля дозволяє виконання довільних команд.",
        "Увімкніть requirepass і закрийте порт файрволом.",
    ),
    9200: _rule(
        SEVERITY_MEDIUM,
        "Elasticsearch доступний без проксі",
        "Elasticsearch часто залишається без автентифікації.",
        "Використовуйте автентифікацію та обмежте мережевий доступ.",
    ),
    3389: _rule(
        SEVERITY_MEDIUM,
        "RDP виставлений",
        "RDP у мережі — часта ціль брутфорсу та експлойтів.",
        "Обмежте доступ, увімкніть NLA, використовуйте VPN.",
    ),
    6000: _rule(
        SEVERITY_HIGH,
        "X11 (X Window) виставлений",
        "X11 може дозволити перехоплення вводу/екрану.",
        "Вимкніть X11-forwarding або обмежте доступ.",
    ),
}


RULE_BY_SERVICE: dict[str, FindingRule] = {
    "telnet": RULE_BY_PORT[23],
    "ms-sql": RULE_BY_PORT[1433],
    "vnc": RULE_BY_PORT[5900],
    "mongod": RULE_BY_PORT[27017],
    "redis": RULE_BY_PORT[6379],
}


def _web_rule(port: int) -> FindingRule:
    return _rule(
        SEVERITY_INFO,
        f"Веб-сервіс на порту {port}",
        "Виявлено відкритий веб-порт; рекомендовано перевірити заголовки та TLS.",
        "Налаштуйте HTTPS, оновлюйте веб-сервер, видаліть непотрібні сторінки.",
    )


def _ssh_rule() -> FindingRule:
    return _rule(
        SEVERITY_LOW,
        "SSH відкритий",
        "SSH доступний; ризик залежить від версії та налаштувань.",
        "Вимкніть автентифікацію паролем або використовуйте ключі.",
    )


def _generic_rule(port: int) -> FindingRule:
    return _rule(
        SEVERITY_LOW,
        f"Відкритий порт {port}",
        "Порт відкритий поза контролем; сервіс не пізнаний.",
        "Переконайтесь, що службу дійсно необхідно видавати на назовні.",
    )


def _rule_for(port: int, service: str) -> FindingRule:
    srv = (service or "").lower().strip()
    if srv in RULE_BY_SERVICE:
        return RULE_BY_SERVICE[srv]
    if port in RULE_BY_PORT:
        return RULE_BY_PORT[port]
    if srv.startswith("ssh"):
        return _ssh_rule()
    if srv.startswith(("http", "https")):
        return _web_rule(port)
    return _generic_rule(port)


def extract_open_services(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    services: list[dict[str, Any]] = []
    for host in parsed.get("hosts", []):
        for port in host.get("ports", []):
            if port.get("state") != "open":
                continue
            services.append(
                {
                    "host": host.get("address", ""),
                    "port": int(port.get("port", 0)),
                    "protocol": port.get("protocol", ""),
                    "state": "open",
                    "service": port.get("service"),
                    "product": port.get("product"),
                    "version": port.get("version"),
                    "cpe": port.get("cpe"),
                }
            )
    return services


def derive_findings(services: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for index, svc in enumerate(services):
        rule = _rule_for(int(svc.get("port", 0)), svc.get("service") or "")
        findings.append(
            {
                "service_index": index,
                "severity": rule["severity"],
                "title": rule["title"],
                "description": rule["description"],
                "recommendation": rule["recommendation"],
                "cve": rule.get("cve"),
            }
        )
    return findings


def compute_risk_score(findings: list[dict[str, Any]]) -> int:
    total = sum(RISK_WEIGHTS.get(f.get("severity", SEVERITY_INFO), 1) for f in findings)
    return min(total, 100)


def risk_level_from_score(score: int) -> str:
    if score >= 75:
        return RISK_LEVEL_CRITICAL
    if score >= 45:
        return RISK_LEVEL_HIGH
    if score >= 20:
        return RISK_LEVEL_MEDIUM
    return RISK_LEVEL_LOW