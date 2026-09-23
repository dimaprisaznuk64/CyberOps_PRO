from __future__ import annotations

import pytest

from services.scanner.nmap_runner import (
    NmapError,
    build_command,
    parse_nmap_xml,
)

SAMPLE_XML = """<?xml version="1.0"?>
<nmaprun scanner="nmap" args="nmap -sT -oX - 127.0.0.1">
  <host>
    <status state="up"/>
    <address addr="127.0.0.1" addrtype="ipv4"/>
    <hostnames><hostname name="localhost" type="PTR"/></hostnames>
    <ports>
      <port protocol="tcp" portid="22">
        <state state="open"/>
        <service name="ssh" product="OpenSSH" version="9.0">
          <cpe>cpe:/a:openbsd:openssh:9.0</cpe>
        </service>
      </port>
      <port protocol="tcp" portid="80">
        <state state="closed"/>
        <service name="http"/>
      </port>
    </ports>
  </host>
</nmaprun>
"""


def test_build_command_tcp_with_ports():
    cmd = build_command("192.168.1.1", "tcp", "22,80")
    assert cmd[0] == "nmap"
    assert "-sT" in cmd
    assert cmd[-1] == "192.168.1.1"
    i = cmd.index("-p")
    assert cmd[i + 1] == "22,80"


def test_build_command_ping():
    cmd = build_command("10.0.0.1", "ping")
    assert "-sn" in cmd


def test_build_command_unknown_type():
    with pytest.raises(NmapError):
        build_command("10.0.0.1", "udp-flood")


def test_parse_nmap_xml():
    result = parse_nmap_xml(SAMPLE_XML)
    assert len(result["hosts"]) == 1
    host = result["hosts"][0]
    assert host["address"] == "127.0.0.1"
    assert host["status"] == "up"
    assert host["hostname"] == "localhost"
    assert len(host["ports"]) == 2
    ssh = next(p for p in host["ports"] if p["port"] == 22)
    assert ssh["state"] == "open"
    assert ssh["service"] == "ssh"
    assert ssh["product"] == "OpenSSH"
    assert ssh["version"] == "9.0"
    assert ssh["cpe"] == "cpe:/a:openbsd:openssh:9.0"


def test_parse_invalid_xml():
    with pytest.raises(NmapError):
        parse_nmap_xml("not-xml")
