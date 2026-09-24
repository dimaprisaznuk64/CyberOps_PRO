"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { AIExplain } from "@/components/AIExplain";
import { RequireAuth } from "@/components/RequireAuth";
import { RiskPill, SeverityPill, StatusPill } from "@/components/Pills";
import { StatCard } from "@/components/StatCard";
import { get } from "@/lib/api";
import type { Finding, ScanResult, ScanRisk, Service } from "@/lib/types";

export default function ScanDetailPage() {
  const params = useParams<{ id: string }>();
  const scanId = Number(params.id);

  const [scan, setScan] = useState<ScanResult | null>(null);
  const [services, setServices] = useState<Service[]>([]);
  const [risk, setRisk] = useState<ScanRisk | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, svc, r, f] = await Promise.all([
        get<ScanResult>(`/api/v1/scans/${scanId}`),
        get<Service[]>(`/api/v1/scans/${scanId}/services`),
        get<ScanRisk>(`/api/v1/scans/${scanId}/risk`),
        get<Finding[]>(`/api/v1/findings?scan_id=${scanId}`),
      ]);
      setScan(s);
      setServices(svc);
      setRisk(r);
      setFindings(f);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Помилка");
    }
  }, [scanId]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <RequireAuth>
      {error && <div className="error">{error}</div>}
      <h2 className="page-title">Сканування #{scanId}</h2>

      {scan && (
        <div className="grid cols-4">
          <StatCard
            label="Статус"
            value={
              <span>
                <StatusPill status={scan.status} />
              </span>
            }
          />
          <StatCard label="Сервіси" value={risk?.services_count ?? "—"} />
          <StatCard label="Risk score" value={risk?.risk_score ?? "—"} />
          <StatCard
            label="Risk level"
            value={
              <span>
                <RiskPill risk={risk?.risk_level} />
              </span>
            }
          />
        </div>
      )}

      {scan?.command && (
        <div className="panel">
          <h3>Команда</h3>
          <code className="small">{scan.command}</code>
        </div>
      )}

      <div className="grid cols-2">
        <div className="panel">
          <h3>Сервіси ({services.length})</h3>
          {services.length === 0 && <div className="empty">Немає даних</div>}
          <table>
            <thead>
              <tr>
                <th>Порт</th>
                <th>Протокол</th>
                <th>Сервіс</th>
                <th>Продукт</th>
                <th>Версія</th>
              </tr>
            </thead>
            <tbody>
              {services.map((s) => (
                <tr key={s.id}>
                  <td>{s.port}</td>
                  <td>{s.protocol}</td>
                  <td>{s.service ?? "—"}</td>
                  <td>{s.product ?? "—"}</td>
                  <td>{s.version ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="panel">
          <h3>Findings по серйозності</h3>
          {risk && (
            <table>
              <tbody>
                {Object.entries(risk.findings_by_severity).map(([sev, count]) => (
                  <tr key={sev}>
                    <td>
                      <SeverityPill severity={sev} />
                    </td>
                    <td>{count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {risk && Object.keys(risk.findings_by_severity).length === 0 && (
            <div className="empty">Немає findings</div>
          )}
        </div>
      </div>

      <div className="panel">
        <h3>Findings ({findings.length})</h3>
        {findings.length === 0 && <div className="empty">Немає findings</div>}
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Серйозність</th>
              <th>Назва</th>
              <th>Рекомендація</th>
              <th>AI</th>
            </tr>
          </thead>
          <tbody>
            {findings.map((f) => (
              <tr key={f.id}>
                <td>{f.id}</td>
                <td>
                  <SeverityPill severity={f.severity} />
                </td>
                <td>
                  <b>{f.title}</b>
                  {f.description && <div className="small muted">{f.description}</div>}
                </td>
                <td className="small">{f.recommendation ?? "—"}</td>
                <td>
                  <AIExplain findingId={f.id} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </RequireAuth>
  );
}