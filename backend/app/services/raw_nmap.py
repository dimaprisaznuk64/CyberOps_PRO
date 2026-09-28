"""Архів сирих nmap-результатів: стиснення, відновлення, метадані.

Сирий XML потрібен як доказ: з нього видно те, чого немає в розпарсеному
result (версія nmap, NSE-вивід, рядки, які обрізав наш парсер). Але в базі це
найбільша колонка, тому архів зберігається gzip-ом, а метадані (розмір,
sha256) рахуються один раз при записі й не вимагають розпакування.
"""

from __future__ import annotations

import gzip
import hashlib
from typing import Any

from app.models.scan import Scan

# Мультимедіа-типи для віддачі архіву
RAW_XML_MEDIA_TYPE = "application/xml"


class RawArchiveError(Exception):
    pass


def pack_raw_xml(xml_text: str) -> tuple[bytes, int, str]:
    """XML -> (gz-байти, розмір оригіналу в байтах, sha256 оригіналу)."""
    raw = xml_text.encode("utf-8")
    # mtime=0 щоб однаковий вміст давав однакові байти (детерміновано для тестів).
    return gzip.compress(raw, compresslevel=6, mtime=0), len(raw), hashlib.sha256(raw).hexdigest()


def unpack_raw_xml(scan: Scan) -> str | None:
    """Повертає сирий XML сканування або None, якщо архіву немає.

    Сумісність із рядками до міграції 0007: там архів лежить у plain Text.
    """
    if scan.raw_xml_gz is not None:
        try:
            return gzip.decompress(scan.raw_xml_gz).decode("utf-8")
        except (OSError, EOFError, UnicodeDecodeError) as exc:
            # Битий стис — не 500 на читанні: скан лишається доступним.
            raise RawArchiveError(f"Не вдалося розпакувати архів: {exc}") from exc
    return scan.raw_xml


def raw_xml_filename(scan: Scan) -> str:
    host = "scan"
    result = scan.result or {}
    hosts = result.get("hosts") or []
    if hosts and isinstance(hosts[0], dict):
        host = str(hosts[0].get("address") or host).replace(":", "-").replace("/", "-")
    return f"nmap-{host}-{scan.id}.xml"


def archive_metadata(scan: Scan, xml_text: str | None) -> dict[str, Any]:
    """Метадані архіву для UI та перевірки цілісності.

    Розмір і sha256 рахуються з реальних байт, а не з окремої колонки: дубльоване
    значення рано чи пізно розійдеться з вмістом, а для архіву доказу це неприйнятно.
    """
    if xml_text is None:
        return {
            "available": False,
            "size_bytes": 0,
            "sha256": "",
            "nmap_version": "",
            "nmap_args": "",
            "hosts_count": 0,
        }
    raw = xml_text.encode("utf-8")
    result = scan.result or {}
    hosts = result.get("hosts") or []
    return {
        "available": True,
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "nmap_version": str(result.get("nmap_version") or ""),
        "nmap_args": str(result.get("nmap_args") or result.get("command") or ""),
        "hosts_count": len(hosts),
    }
