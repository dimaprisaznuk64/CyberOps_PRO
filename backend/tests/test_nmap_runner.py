from __future__ import annotations

import pytest
from services.scanner.nmap_runner import (
    MAX_SCRIPT_OUTPUT_CHARS,
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

# Те саме, але з «deep»-шарами, які nmap пише у XML, а старий парсер викидав.
DEEP_XML = """<?xml version="1.0"?>
<nmaprun scanner="nmap" args="nmap -sT -sV -oX - 10.0.0.5" version="7.95" start="1758000000">
  <scaninfo type="connect" protocol="tcp" numservices="1000"/>
  <host>
    <status state="up" reason="echo-reply"/>
    <address addr="10.0.0.5" addrtype="ipv4"/>
    <hostnames>
      <hostname name="web.local" type="PTR"/>
      <hostname name="alt.local" type="user"/>
    </hostnames>
    <ports>
      <port protocol="tcp" portid="443">
        <state state="open" reason="syn-ack"/>
        <service name="https" product="nginx" version="1.25.3" tunnel="ssl">
          <cpe>cpe:/a:igor_sysoev:nginx:1.25.3</cpe>
        </service>
        <script id="ssl-cert" output="Subject: commonName=web.local">
          <elem key="subject">CN=web.local</elem>
          <elem key="notAfter">2026-01-01T00:00:00</elem>
        </script>
      </port>
    </ports>
    <os>
      <osmatch name="Linux 5.X" accuracy="95" osfamily="Linux"/>
      <osmatch name="Linux 4.X" accuracy="88" osfamily="Linux"/>
    </os>
    <uptime seconds="12345"/>
    <distance value="1"/>
    <hostscript>
      <script id="smb-os-discovery" output="OS: Windows"/>
    </hostscript>
  </host>
  <runstats>
    <finished time="1758000060" timestr="Mon Sep 28 12:00:00" elapsed="60.5" summary="Nmap done"/>
    <hosts up="1" down="2" total="3"/>
  </runstats>
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


def test_parse_keeps_deep_nmap_layers():
    """Версія nmap, scaninfo, усі hostname'и, OS, NSE-скрипти і runstats.

    Це те, що лежить у самому XML, але губилося при парсингу — без нього
    «архів» сторінки сканування не мав би чого показувати.
    """
    result = parse_nmap_xml(DEEP_XML)
    assert result["nmap_version"] == "7.95"
    assert result["nmap_args"] == "nmap -sT -sV -oX - 10.0.0.5"
    assert result["scaninfo"] == {"type": "connect", "protocol": "tcp", "num_services": 1000}

    host = result["hosts"][0]
    assert [hn["name"] for hn in host["hostnames"]] == ["web.local", "alt.local"]
    assert host["status_reason"] == "echo-reply"
    assert [os_match["name"] for os_match in host["os_matches"]] == [
        "Linux 5.X",
        "Linux 4.X",
    ]
    assert host["os_matches"][0]["accuracy"] == 95
    assert host["uptime"] == "12345"
    assert host["distance"] == "1"
    assert host["host_scripts"][0]["id"] == "smb-os-discovery"

    port = host["ports"][0]
    assert port["scripts"][0]["id"] == "ssl-cert"
    assert port["scripts"][0]["output"] == "Subject: commonName=web.local"
    assert port["scripts"][0]["elements"]["subject"] == "CN=web.local"

    assert result["stats"]["elapsed"] == 60.5
    assert result["stats"]["hosts_up"] == 1
    assert result["stats"]["hosts_total"] == 3


def test_parse_keeps_first_hostname_for_backward_compat():
    result = parse_nmap_xml(DEEP_XML)
    assert result["hosts"][0]["hostname"] == "web.local"


def test_parse_clips_long_script_output():
    """NSE-банер може бути на десятки кілобайт — у JSON має потрапити обрізаним."""
    banner = "A" * (MAX_SCRIPT_OUTPUT_CHARS + 500)
    xml = f"""<?xml version="1.0"?>
    <nmaprun scanner="nmap" version="7.95">
      <host>
        <status state="up"/>
        <address addr="10.0.0.5" addrtype="ipv4"/>
        <ports>
          <port protocol="tcp" portid="21">
            <state state="open"/>
            <service name="ftp"/>
            <script id="banner" output="{banner}"/>
          </port>
        </ports>
      </host>
    </nmaprun>
    """
    output = parse_nmap_xml(xml)["hosts"][0]["ports"][0]["scripts"][0]["output"]
    assert len(output) < len(banner)
    assert "+500 симв." in output


def test_parse_without_optional_layers():
    """Мінімальний XML без scaninfo/runstats не має ламати KeyError."""
    result = parse_nmap_xml(SAMPLE_XML)
    assert "scaninfo" not in result
    assert "stats" not in result
    assert result["hosts"][0]["os_matches"] == []
    assert "scripts" not in result["hosts"][0]["ports"][0]


def test_parse_rejects_entity_expansion():
    """XML приходить від сканованої цілі, тож billion laughs має бути відкинуто."""
    bomb = (
        '<?xml version="1.0"?>'
        "<!DOCTYPE lolz [<!ENTITY lol 'lol'>"
        '<!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">'
        '<!ENTITY lol2 "&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;">'
        "]>"
        '<nmaprun><host><status state="&lol2;"/></host></nmaprun>'
    )
    with pytest.raises(NmapError):
        parse_nmap_xml(bomb)
