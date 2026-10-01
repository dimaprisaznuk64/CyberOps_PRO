"use client";

import { useCallback, useEffect, useState } from "react";

import { download, get } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { NmapHost, NmapScript, ScanRaw } from "@/lib/types";

function formatBytes(bytes: number, units: { b: string; kb: string; mb: string }): string {
  if (bytes < 1024) return `${bytes} ${units.b}`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} ${units.kb}`;
  return `${(bytes / 1024 / 1024).toFixed(2)} ${units.mb}`;
}

function ScriptList({ scripts, label }: { scripts: NmapScript[]; label: string }) {
  return (
    <div className="small muted" style={{ marginTop: 4 }}>
      {label}
      {scripts.map((s) => (
        <div key={s.id}>
          <code>{s.id}</code>
          {s.output && <span> — {s.output}</span>}
          {s.elements &&
            Object.entries(s.elements).map(([key, value]) => (
              <div key={key} className="muted">
                {key}: {value}
              </div>
            ))}
        </div>
      ))}
    </div>
  );
}

function HostCard({ host }: { host: NmapHost }) {
  const { t } = useI18n();
  const names = host.hostnames?.length ? host.hostnames : [{ name: host.hostname, type: "" }];
  return (
    <div className="panel" style={{ marginBottom: 12 }}>
      <h3 style={{ marginBottom: 8 }}>
        {host.address || "—"}
        {host.status && (
          <span className={`pill ${host.status === "up" ? "ok" : "neutral"}`} style={{ marginLeft: 8 }}>
            {host.status}
          </span>
        )}
        {host.status_reason && <span className="small muted"> · {host.status_reason}</span>}
      </h3>

      <div className="small">
        {names
          .filter((n) => n.name)
          .map((n) => (
            <div key={`${n.type}-${n.name}`}>
              {n.name}
              {n.type && <span className="muted"> ({n.type})</span>}
            </div>
          ))}
        {!names.some((n) => n.name) && <div className="muted">{t("raw.hostnameUnknown")}</div>}
        {(host.uptime || host.distance) && (
          <div className="muted">
            {host.uptime && `uptime ${host.uptime}s`}
            {host.uptime && host.distance && " · "}
            {host.distance && `distance ${host.distance}`}
          </div>
        )}
      </div>

      {host.os_matches?.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>{t("raw.osFingerprint")}</th>
              <th>{t("raw.family")}</th>
              <th>{t("raw.accuracy")}</th>
            </tr>
          </thead>
          <tbody>
            {host.os_matches.map((os) => (
              <tr key={`${os.name}-${os.accuracy}`}>
                <td>{os.name}</td>
                <td className="muted">{os.family || "—"}</td>
                <td>{os.accuracy}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {host.host_scripts && host.host_scripts.length > 0 && (
        <ScriptList scripts={host.host_scripts} label={t("raw.hostScripts")} />
      )}

      {host.ports.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>{t("raw.colPort")}</th>
              <th>{t("raw.colService")}</th>
              <th>NSE</th>
            </tr>
          </thead>
          <tbody>
            {host.ports.map((p) => (
              <tr key={`${p.protocol}-${p.port}`}>
                <td>
                  {p.port}/{p.protocol}
                  <span className="muted small"> {p.state}</span>
                </td>
                <td className="small">
                  {p.service || "—"}
                  {p.product && <div className="muted">{p.product}</div>}
                  {p.cpe && <div className="muted">{p.cpe}</div>}
                </td>
                <td className="small">
                  {p.scripts && p.scripts.length > 0 ? (
                    <ScriptList scripts={p.scripts} label="" />
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function ScanRawArchive({ scanId, status }: { scanId: number; status?: string }) {
  const { t } = useI18n();
  const [raw, setRaw] = useState<ScanRaw | null>(null);
  const [xml, setXml] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Метадані + «deep»-розбір важать малі, сам XML тягнемо лише за кліком:
  // -sV з NSE на /24 — це мегабайти, які не варто вантажити в кожну сесію.
  useEffect(() => {
    let cancelled = false;
    get<ScanRaw>(`/api/v1/scans/${scanId}/raw?include_xml=false`)
      .then((data) => {
        if (!cancelled) setRaw(data);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : t("common.error"));
      });
    return () => {
      cancelled = true;
    };
  }, [scanId, t]);

  const showXml = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const data = await get<ScanRaw>(`/api/v1/scans/${scanId}/raw`);
      setRaw(data);
      setXml(data.xml);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }, [scanId, t]);

  const save = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await download(`/api/v1/scans/${scanId}/raw.xml`, `nmap-scan-${scanId}.xml`);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("raw.downloadFailed"));
    } finally {
      setBusy(false);
    }
  }, [scanId, t]);

  const filename = `nmap-scan-${scanId}.xml`;

  return (
    <div className="panel">
      <h3>{t("raw.title")}</h3>
      {error && <div className="error">{error}</div>}

      {raw && !raw.available && (
        <div className="empty">
          {t("raw.notAvailable")}
          {status ? t("raw.notAvailableStatus", { status }) : ""}
          {t("raw.notAvailableTail")}
        </div>
      )}

      {raw?.available && (
        <>
          <div className="form-row">
            <div>
              <label>{t("raw.nmap")}</label>
              <div className="small">{raw.nmap_version || t("raw.unknown")}</div>
            </div>
            <div>
              <label>{t("raw.size")}</label>
              <div className="small">
                {formatBytes(raw.size_bytes, {
                  b: t("raw.bytes.b"),
                  kb: t("raw.bytes.kb"),
                  mb: t("raw.bytes.mb"),
                })}
                {raw.compressed && <span className="muted"> · gzip</span>}
              </div>
            </div>
            <div>
              <label>{t("raw.hosts")}</label>
              <div className="small">{raw.hosts_count}</div>
            </div>
            <div>
              <label>SHA-256</label>
              <div className="small" title={raw.sha256}>
                <code>{raw.sha256.slice(0, 16)}…</code>
              </div>
            </div>
          </div>

          {raw.nmap_args && (
            <div className="small muted" style={{ marginBottom: 8 }}>
              <code>{raw.nmap_args}</code>
            </div>
          )}

          {raw.parsed?.scaninfo && (
            <div className="small muted" style={{ marginBottom: 8 }}>
              {raw.parsed.scaninfo.type}/{raw.parsed.scaninfo.protocol}
              {raw.parsed.scaninfo.num_services
                ? ` · ${t("raw.portsCount", { count: raw.parsed.scaninfo.num_services })}`
                : ""}
              {raw.parsed.stats?.hosts_total !== undefined &&
                ` · ${t("raw.stats", {
                  up: raw.parsed.stats.hosts_up ?? 0,
                  down: raw.parsed.stats.hosts_down ?? 0,
                  total: raw.parsed.stats.hosts_total,
                })}`}
              {raw.parsed.stats?.elapsed ? ` · ${raw.parsed.stats.elapsed}s` : ""}
            </div>
          )}

          {raw.parsed?.hosts.map((host) => (
            <HostCard key={host.address || host.hostname} host={host} />
          ))}

          <div className="form-row" style={{ marginTop: 8, marginBottom: 0 }}>
            <div style={{ flex: "0 0 auto" }}>
              <button className="ghost sm" onClick={save} disabled={busy}>
                {t("raw.downloadXml")}
              </button>
            </div>
            <div style={{ flex: "0 0 auto" }}>
              <button className="ghost sm" onClick={showXml} disabled={busy || !!xml}>
                {busy ? t("raw.downloading") : xml ? t("raw.xmlShown") : t("raw.showXml")}
              </button>
            </div>
            {raw.truncated && <div className="small muted">{t("raw.truncated")}</div>}
          </div>

          {xml && <pre className="codeblock">{xml}</pre>}
        </>
      )}

      {!raw && !error && <div className="empty">{t("raw.loadingArchive")}</div>}
      <div className="small muted" style={{ marginTop: 6 }}>
        {t("raw.file")}
        <code>{filename}</code>
      </div>
    </div>
  );
}
