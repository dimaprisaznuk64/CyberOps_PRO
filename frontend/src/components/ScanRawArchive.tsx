"use client";

import { useCallback, useEffect, useState } from "react";

import { download, get } from "@/lib/api";
import type { NmapHost, NmapScript, ScanRaw } from "@/lib/types";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
  return `${(bytes / 1024 / 1024).toFixed(2)} МБ`;
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
        {!names.some((n) => n.name) && <div className="muted">hostname не визначено</div>}
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
              <th>OS-відпечаток</th>
              <th>Сімейство</th>
              <th>Точність</th>
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
        <ScriptList scripts={host.host_scripts} label="Хост-скрипти:" />
      )}

      {host.ports.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Порт</th>
              <th>Сервіс</th>
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
        if (!cancelled) setError(e instanceof Error ? e.message : "Помилка");
      });
    return () => {
      cancelled = true;
    };
  }, [scanId]);

  const showXml = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const data = await get<ScanRaw>(`/api/v1/scans/${scanId}/raw`);
      setRaw(data);
      setXml(data.xml);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Помилка");
    } finally {
      setBusy(false);
    }
  }, [scanId]);

  const save = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await download(`/api/v1/scans/${scanId}/raw.xml`, `nmap-scan-${scanId}.xml`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не вдалося завантажити файл");
    } finally {
      setBusy(false);
    }
  }, [scanId]);

  const filename = `nmap-scan-${scanId}.xml`;

  return (
    <div className="panel">
      <h3>Сирий Nmap-архів</h3>
      {error && <div className="error">{error}</div>}

      {raw && !raw.available && (
        <div className="empty">
          Сирого Nmap-звіту немає{status ? ` (статус сканування: ${status})` : ""}. Архів
          з’являється після завершення сканування.
        </div>
      )}

      {raw?.available && (
        <>
          <div className="form-row">
            <div>
              <label>Nmap</label>
              <div className="small">{raw.nmap_version || "невідомо"}</div>
            </div>
            <div>
              <label>Розмір</label>
              <div className="small">
                {formatBytes(raw.size_bytes)}
                {raw.compressed && <span className="muted"> · gzip</span>}
              </div>
            </div>
            <div>
              <label>Хостів</label>
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
                ? ` · ${raw.parsed.scaninfo.num_services} портів`
                : ""}
              {raw.parsed.stats?.hosts_total !== undefined &&
                ` · up ${raw.parsed.stats.hosts_up ?? 0} / down ${
                  raw.parsed.stats.hosts_down ?? 0
                } з ${raw.parsed.stats.hosts_total}`}
              {raw.parsed.stats?.elapsed ? ` · ${raw.parsed.stats.elapsed}s` : ""}
            </div>
          )}

          {raw.parsed?.hosts.map((host) => (
            <HostCard key={host.address || host.hostname} host={host} />
          ))}

          <div className="form-row" style={{ marginTop: 8, marginBottom: 0 }}>
            <div style={{ flex: "0 0 auto" }}>
              <button className="ghost sm" onClick={save} disabled={busy}>
                ⬇ Завантажити .xml
              </button>
            </div>
            <div style={{ flex: "0 0 auto" }}>
              <button className="ghost sm" onClick={showXml} disabled={busy || !!xml}>
                {busy ? "Завантаження…" : xml ? "XML показано" : "Показати сирий XML"}
              </button>
            </div>
            {raw.truncated && (
              <div className="small muted">
                XML завеликий для сторінки — повний файл лише у .xml
              </div>
            )}
          </div>

          {xml && <pre className="codeblock">{xml}</pre>}
        </>
      )}

      {!raw && !error && <div className="empty">Завантаження архіву…</div>}
      <div className="small muted" style={{ marginTop: 6 }}>
        Файл: <code>{filename}</code>
      </div>
    </div>
  );
}
