from __future__ import annotations

import ipaddress
import socket

from app.config import settings


class HostNotAllowedError(Exception):
    pass


def resolve_ips(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise HostNotAllowedError(f"Не вдалося розв'язати хост: {host}") from exc
    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if ip not in ips:
            ips.append(ip)
    if not ips:
        raise HostNotAllowedError(f"Порожній результат розв'язування: {host}")
    return ips


def assert_host_allowed(host: str, allow_public: bool | None = None) -> None:
    if allow_public is None:
        allow_public = settings.scan_allow_public
    for ip in resolve_ips(host):
        if not ip.is_loopback and not ip.is_private and not ip.is_link_local:
            if not allow_public:
                raise HostNotAllowedError(
                    f"Публічна адреса заборонена політикою: {ip}. "
                    "Скануйте лише власну інфраструктуру."
                )
