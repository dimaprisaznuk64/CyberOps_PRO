"use client";

import { useState } from "react";

import { post } from "@/lib/api";
import type { AIExplanation } from "@/lib/types";

export function AIExplain({ findingId }: { findingId: number }) {
  const [data, setData] = useState<AIExplanation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await post<AIExplanation>(`/api/v1/findings/${findingId}/explain`);
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Помилка");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      {!data && (
        <button className="sm" onClick={run} disabled={loading}>
          {loading ? "Аналіз…" : "🤖 AI explain"}
        </button>
      )}
      {error && <div className="error">{error}</div>}
      {data && (
        <div className="panel" style={{ marginTop: 10 }}>
          <h3>AI пояснення ({data.provider})</h3>
          <p>
            <b>Що знайдено:</b> {data.explanation}
          </p>
          <p>
            <b>Вплив:</b> {data.impact}
          </p>
          <p>
            <b>Ризик:</b> {data.risk_explanation}
          </p>
          <p>
            <b>Як виправити:</b> {data.remediation}
          </p>
        </div>
      )}
    </div>
  );
}