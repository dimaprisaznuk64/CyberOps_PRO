"""Nmap scanner: побудова команди, запуск, парсинг XML-виводу."""

from __future__ import annotations

import subprocess
from typing import Any

# nmap формує XML у відповідь на дані від сканованої цілі, тож це недовірений
# ввід: defusedxml блокує entity expansion (billion laughs) та зовнішні DTD.
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

SCAN_PRESETS: dict[str, list[str]] = {
    "ping": ["-sn"],
    "tcp": ["-sT", "-sV", "--open"],
    "quick": ["-T4", "--top-ports", "100", "-sV", "--open"],
}

# NSE-скрипти можуть віддавати сотні кілобайт виводу (http-title, ssl-cert,
# banners). Повний сирий XML і так зберігається окремо, а в розпарсений
# результат нам потрібні лише короткі підказки для UI — тому ріжемо.
MAX_SCRIPT_OUTPUT_CHARS = 4000
MAX_SCRIPT_ELEMENTS = 50


class NmapError(Exception):
    pass


def build_command(host: str, scan_type: str = "tcp", ports: str | None = None) -> list[str]:
    if scan_type not in SCAN_PRESETS:
        raise NmapError(f"Невідомий тип сканування: {scan_type}")
    cmd = ["nmap", *SCAN_PRESETS[scan_type]]
    if ports:
        cmd += ["-p", ports]
    cmd.append(host)
    return cmd


def run_nmap(command: list[str], timeout: int = 300) -> str:
    xml_cmd = [*command[:-1], "-oX", "-", command[-1]]
    try:
        proc = subprocess.run(
            xml_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise NmapError("nmap не знайдено в PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise NmapError(f"Сканування перевищило таймаут {timeout}c") from exc
    if proc.returncode not in (0, 1):
        raise NmapError(proc.stderr.strip() or f"nmap завершився з кодом {proc.returncode}")
    return proc.stdout


def _clip(value: str | None, limit: int = MAX_SCRIPT_OUTPUT_CHARS) -> str:
    if not value:
        return ""
    if len(value) <= limit:
        return value
    return f"{value[:limit]}…(+{len(value) - limit} симв.)"


def _parse_scripts(parent: ET.Element) -> list[dict[str, Any]]:
    """NSE-вивід: <script id="..." output="..."><elem key="...">value</elem></script>."""
    scripts: list[dict[str, Any]] = []
    for script in parent.findall("script"):
        entry: dict[str, Any] = {
            "id": script.attrib.get("id", ""),
            "output": _clip(script.attrib.get("output")),
        }
        elements = script.findall("elem")
        if elements:
            entry["elements"] = {
                elem.attrib.get("key", ""): _clip((elem.text or "").strip(), 500)
                for elem in elements[:MAX_SCRIPT_ELEMENTS]
            }
        scripts.append(entry)
    return scripts


def _parse_hosts(root: ET.Element) -> list[dict[str, Any]]:
    hosts: list[dict[str, Any]] = []
    for host in root.findall("host"):
        status_el = host.find("status")
        addr_el = host.find("address")
        hostname_el = host.find("hostnames/hostname")

        hostnames = [
            {"name": hn.attrib.get("name", ""), "type": hn.attrib.get("type", "")}
            for hn in host.findall("hostnames/hostname")
            if hn.attrib.get("name")
        ]

        os_matches = [
            {
                "name": os_match.attrib.get("name", ""),
                "accuracy": int(os_match.attrib.get("accuracy", 0) or 0),
                "family": os_match.attrib.get("osfamily", ""),
            }
            for os_match in host.findall("os/osmatch")
        ]

        ports: list[dict[str, Any]] = []
        for port in host.findall("ports/port"):
            state_el = port.find("state")
            service_el = port.find("service")
            cpe_el = port.find("service/cpe") if service_el is not None else None
            parsed_port: dict[str, Any] = {
                "port": int(port.attrib.get("portid", 0)),
                "protocol": port.attrib.get("protocol", ""),
                "state": state_el.attrib.get("state", "") if state_el is not None else "",
                "service": service_el.attrib.get("name", "") if service_el is not None else "",
                "product": (
                    service_el.attrib.get("product", "") if service_el is not None else ""
                ),
                "version": (
                    service_el.attrib.get("version", "") if service_el is not None else ""
                ),
                "cpe": cpe_el.text.strip() if cpe_el is not None and cpe_el.text else "",
            }
            scripts = _parse_scripts(port)
            if scripts:
                parsed_port["scripts"] = scripts
            ports.append(parsed_port)

        host_entry: dict[str, Any] = {
            "address": addr_el.attrib.get("addr", "") if addr_el is not None else "",
            "status": status_el.attrib.get("state", "") if status_el is not None else "",
            "hostname": (
                hostname_el.attrib.get("name", "") if hostname_el is not None else ""
            ),
            "hostnames": hostnames,
            "os_matches": os_matches,
            "ports": ports,
        }
        if status_el is not None and status_el.attrib.get("reason"):
            host_entry["status_reason"] = status_el.attrib["reason"]
        hostscript_el = host.find("hostscript")
        if hostscript_el is not None:
            host_scripts = _parse_scripts(hostscript_el)
            if host_scripts:
                host_entry["host_scripts"] = host_scripts
        # nmap віддає uptime/distance атрибутами (<uptime seconds="12345"/>),
        # але в старих версіях значення дублюється текстом.
        uptime_el = host.find("uptime")
        if uptime_el is not None:
            host_entry["uptime"] = _clip(
                uptime_el.attrib.get("seconds") or (uptime_el.text or "").strip(), 200
            )
        distance_el = host.find("distance")
        if distance_el is not None:
            host_entry["distance"] = _clip(
                distance_el.attrib.get("value") or (distance_el.text or "").strip(), 200
            )
        hosts.append(host_entry)
    return hosts


def _parse_scaninfo(root: ET.Element) -> dict[str, Any] | None:
    scaninfo = root.find("scaninfo")
    if scaninfo is None:
        return None
    # nmap пише numservices="1000" (кількість) і services="1-1024" (діапазон);
    # для лічильника беремо саме numservices.
    numservices = scaninfo.attrib.get("numservices", "")
    return {
        "type": scaninfo.attrib.get("type", ""),
        "protocol": scaninfo.attrib.get("protocol", ""),
        "num_services": int(numservices) if numservices.isdigit() else None,
    }


def _parse_stats(root: ET.Element) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    finished = root.find("runstats/finished")
    if finished is not None:
        elapsed = finished.attrib.get("elapsed", "")
        stats["elapsed"] = float(elapsed) if elapsed.replace(".", "", 1).isdigit() else None
        stats["finished_at"] = finished.attrib.get("timestr") or finished.attrib.get("time")
    hosts_el = root.find("runstats/hosts")
    if hosts_el is not None:
        for key in ("up", "down", "total"):
            value = hosts_el.attrib.get(key, "")
            if value.isdigit():
                stats[f"hosts_{key}"] = int(value)
    return stats


def parse_nmap_xml(xml_text: str) -> dict[str, Any]:
    """Розбирає nmap -oX у структуру для БД та UI.

    Окрім портів (з чого рахуємо сервіси й findings) зберігаємо «deep»-шари,
    які nmap віддає дрібним шрифтом у самому XML: версія nmap, scaninfo,
    усі hostname'и, OS-відпечатки, NSE-вивід скриптів і runstats.
    """

    try:
        root = ET.fromstring(xml_text)
    except (ET.ParseError, DefusedXmlException) as exc:
        raise NmapError(f"Невалідний XML від nmap: {exc}") from exc

    args = root.attrib.get("args", "")
    result: dict[str, Any] = {
        "command": root.attrib.get("startstr") or args,
        "nmap_args": args,
        "nmap_version": root.attrib.get("version", ""),
        "nmap_start": root.attrib.get("start", ""),
        "hosts": _parse_hosts(root),
    }
    scaninfo = _parse_scaninfo(root)
    if scaninfo is not None:
        result["scaninfo"] = scaninfo
    stats = _parse_stats(root)
    if stats:
        result["stats"] = stats
    return result
