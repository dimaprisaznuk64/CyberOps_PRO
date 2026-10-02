#!/usr/bin/env python3
"""End-to-end demo через API Gateway:
register -> login -> asset -> scan -> findings -> AI explain -> report -> dashboard.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE = "http://localhost:8000"


class DemoError(Exception):
    pass


def _request(
    base: str,
    method: str,
    path: str,
    token: str | None = None,
    data=None,
    timeout: int = 30,
):
    body = None
    headers = {}
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            ct = resp.headers.get("Content-Type", "")
            return json.loads(raw) if "json" in ct else raw
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")
        except Exception:
            pass
        raise DemoError(f"HTTP {exc.code} {method} {path}: {detail[:300]}") from exc


def run(
    base: str,
    username: str,
    password: str,
    host: str,
    wait: int,
    admin_username: str,
    admin_password: str,
) -> None:
    print(f"[1/8] health -> {base}/health")
    health = _request(base, "GET", "/health")
    print(f"      {health}")

    print(f"[2/8] register ({username})")
    try:
        _request(base, "POST", "/api/v1/auth/register", data={
            "username": username, "password": password,
        })
        print("      registered (role=user — публічна реєстрація не приймає роль)")
    except DemoError as exc:
        print(f"      register: {exc} (login instead)")

    # Роль analyst більше не можна попросити в реєстрації, тож піднімати її
    # доводиться через адміністратора. Це не декоративний крок: він проходить
    # той самий шлях, який єдиний доступний у системі.
    print(f"[3/8] promote to analyst via {admin_username}")
    admin_token = _request(base, "POST", "/api/v1/auth/login", data={
        "username": admin_username, "password": admin_password,
    })["access_token"]
    users = _request(base, "GET", "/api/v1/users", token=admin_token)
    target = next((u for u in users if u["username"] == username), None)
    if target is None:
        raise DemoError(f"користувача {username} немає серед /users")
    if target["role"] != "analyst":
        _request(base, "PATCH", f"/api/v1/users/{target['id']}/role", token=admin_token,
                 data={"role": "analyst"})
    print(f"      {username} -> analyst")

    print("[4/8] login")
    tokens = _request(base, "POST", "/api/v1/auth/login", data={
        "username": username, "password": password,
    })
    token = tokens["access_token"]
    print("      access_token ok")

    print(f"[5/8] create asset host={host}")
    asset = _request(base, "POST", "/api/v1/assets", token=token, data={
        "name": f"demo-{host}", "host": host, "kind": "hostname", "description": "auto demo target",
    })
    asset_id = asset["id"]
    print(f"      asset #{asset_id}")

    print("[6/8] start scan")
    scan = _request(base, "POST", "/api/v1/scans", token=token, data={
        "asset_id": asset_id, "scan_type": "tcp",
    })
    scan_id = scan["id"]
    print(f"      scan #{scan_id} queued")

    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        time.sleep(3)
        state = _request(base, "GET", f"/api/v1/scans/{scan_id}", token=token)
        print(f"      status={state['status']}")
        if state["status"] in ("done", "failed", "cancelled"):
            break

    print("[7/8] findings + AI explanation")
    findings = _request(base, "GET", "/api/v1/findings", token=token)
    if findings:
        f0 = findings[0]
        print(f"      {len(findings)} findings, first: {f0['severity']} — {f0['title']}")
        ai = _request(base, "POST", f"/api/v1/findings/{f0['id']}/explain", token=token)
        print(f"      AI ({ai['provider']}): {ai['explanation']}")
        print(f"      impact: {ai['impact']}")
        print(f"      risk:   {ai['risk_explanation']}")
        print(f"      fix:    {ai['remediation']}")
    else:
        print("      no findings yet (worker/scanner didn't produce results)")

    print("[8/8] report + dashboard")
    report = _request(base, "POST", "/api/v1/reports", token=token, data={
        "title": "Demo scan report", "report_type": "scan", "scan_id": scan_id,
    })
    print(f"      report #{report['id']} created")
    dashboard = _request(base, "GET", "/api/v1/dashboard", token=token)
    print(f"      dashboard: assets={dashboard.get('total_assets')}, "
          f"high_risk_scans={dashboard.get('high_risk_scans')}, "
          f"unread={dashboard.get('unread_notifications')}, "
          f"recent_scans={len(dashboard.get('recent_scans') or [])}")

    print("DONE")


def main() -> None:
    parser = argparse.ArgumentParser(description="CyberOps PRO demo")
    parser.add_argument(
        "--base", default=DEFAULT_BASE, help=f"gateway URL (default {DEFAULT_BASE})"
    )
    parser.add_argument("--username", default=f"demo_{int(time.time())}", help="demo username")
    parser.add_argument("--password", default="DemoPass123", help="demo password")
    parser.add_argument(
        "--host",
        default="vulnerable-api",
        help="scan target; with security-lab up use vulnerable-api/vulnerable-web/test-db",
    )
    parser.add_argument("--wait", type=int, default=90, help="max wait seconds for scan")
    parser.add_argument("--admin-username", default=os.environ.get("ADMIN_USERNAME", "admin"),
                        help="admin, created at auth startup from ADMIN_USERNAME/ADMIN_PASSWORD")
    parser.add_argument("--admin-password", default=os.environ.get("ADMIN_PASSWORD", "admin"),
                        help="admin password (set ADMIN_PASSWORD env to override)")
    args = parser.parse_args()
    try:
        run(args.base, args.username, args.password, args.host, args.wait,
            args.admin_username, args.admin_password)
    except DemoError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()