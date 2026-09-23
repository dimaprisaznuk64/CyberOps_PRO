from __future__ import annotations

from app.services.analysis import (
    RISK_LEVEL_CRITICAL,
    RISK_LEVEL_HIGH,
    RISK_LEVEL_LOW,
    RISK_LEVEL_MEDIUM,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    compute_risk_score,
    derive_findings,
    extract_open_services,
    risk_level_from_score,
)

PARSED = {
    "hosts": [
        {
            "address": "127.0.0.1",
            "summary": "",
            "ports": [
                {
                    "port": 22,
                    "protocol": "tcp",
                    "state": "open",
                    "service": "ssh",
                    "product": "OpenSSH",
                    "version": "9.0",
                    "cpe": "cpe:/a:openbsd:openssh:9.0",
                },
                {
                    "port": 23,
                    "protocol": "tcp",
                    "state": "open",
                    "service": "telnet",
                    "product": "",
                    "version": "",
                    "cpe": "",
                },
                {
                    "port": 80,
                    "protocol": "tcp",
                    "state": "closed",
                    "service": "http",
                    "product": "",
                    "version": "",
                    "cpe": "",
                },
            ],
        }
    ]
}


def test_extract_open_services_filters_closed_ports():
    services = extract_open_services(PARSED)
    assert len(services) == 2
    assert all(s["state"] == "open" for s in services)
    assert services[0]["port"] == 22
    assert services[1]["port"] == 23


def test_derive_findings_uses_rules():
    services = extract_open_services(PARSED)
    findings = derive_findings(services)
    by_severity = {f["severity"] for f in findings}
    assert SEVERITY_HIGH in by_severity
    assert SEVERITY_LOW in by_severity
    telnet = next(f for f in findings if f["service_index"] == 1)
    assert telnet["severity"] == SEVERITY_HIGH
    assert "telnet" in telnet["title"].lower()
    assert telnet["recommendation"]


def test_compute_risk_score_and_level():
    services = extract_open_services(PARSED)
    findings = derive_findings(services)
    score = compute_risk_score(findings)
    assert score > 0
    assert score <= 100
    assert risk_level_from_score(score) in (
        RISK_LEVEL_LOW,
        RISK_LEVEL_MEDIUM,
        RISK_LEVEL_HIGH,
        RISK_LEVEL_CRITICAL,
    )


def test_risk_level_thresholds():
    assert risk_level_from_score(0) == RISK_LEVEL_LOW
    assert risk_level_from_score(25) == RISK_LEVEL_MEDIUM
    assert risk_level_from_score(50) == RISK_LEVEL_HIGH
    assert risk_level_from_score(90) == RISK_LEVEL_CRITICAL