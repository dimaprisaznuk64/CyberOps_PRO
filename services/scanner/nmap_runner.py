"""Nmap scanner: побудова команди, запуск, парсинг XML-виводу."""

from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from typing import Any

SCAN_PRESETS: dict[str, list[str]] = {
    "ping": ["-sn"],
    "tcp": ["-sT", "-sV", "--open"],
    "quick": ["-T4", "--top-ports", "100", "-sV", "--open"],
}


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


def parse_nmap_xml(xml_text: str) -> dict[str, Any]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise NmapError(f"Невалідний XML від nmap: {exc}") from exc

    result: dict[str, Any] = {
        "command": root.attrib.get("startstr") or root.attrib.get("args", ""),
        "hosts": [],
    }
    for host in root.findall("host"):
        status_el = host.find("status")
        addr_el = host.find("address")
        hostname_el = host.find("hostnames/hostname")

        ports: list[dict[str, Any]] = []
        for port in host.findall("ports/port"):
            state_el = port.find("state")
            service_el = port.find("service")
            cpe_el = port.find("service/cpe") if service_el is not None else None
            ports.append(
                {
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
            )

        result["hosts"].append(
            {
                "address": addr_el.attrib.get("addr", "") if addr_el is not None else "",
                "status": status_el.attrib.get("state", "") if status_el is not None else "",
                "hostname": (
                    hostname_el.attrib.get("name", "") if hostname_el is not None else ""
                ),
                "ports": ports,
            }
        )
    return result
