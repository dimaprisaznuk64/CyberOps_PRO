from __future__ import annotations

from prometheus_client import REGISTRY, Counter, Histogram, generate_latest

http_requests_total = Counter(
    "http_requests_total",
    "HTTP requests processed",
    ["method", "path", "status"],
)
scan_duration_seconds = Histogram(
    "scan_duration_seconds",
    "Nmap scan duration in seconds",
    ["scan_type"],
)
scan_results_total = Counter(
    "scan_results_total",
    "Finished scans by status and risk level",
    ["status", "risk_level"],
)
scan_services_total = Counter(
    "scan_services_total",
    "Discovered open services",
    ["scan_type"],
)
notifications_delivered_total = Counter(
    "notifications_delivered_total",
    "Notification delivery attempts by channel and status",
    ["channel", "status"],
)


def describe_path(path: str) -> str:
    parts = path.strip("/").split("/")
    return "/" + "/".join(parts[:3])


def render_metrics() -> bytes:
    return generate_latest(REGISTRY)