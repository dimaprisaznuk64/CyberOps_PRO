"use client";

import { useState } from "react";

import { post } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { AIExplanation } from "@/lib/types";

export function AIExplain({ findingId }: { findingId: number }) {
  const { t } = useI18n();
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
      setError(e instanceof Error ? e.message : t("common.error"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      {!data && (
        <button className="sm" onClick={run} disabled={loading}>
          {loading ? t("ai.analyzing") : t("ai.button")}
        </button>
      )}
      {error && <div className="error">{error}</div>}
      {data && (
        <div className="panel" style={{ marginTop: 10 }}>
          <h3>{t("ai.title", { provider: data.provider })}</h3>
          <p>
            <b>{t("ai.found")}</b> {data.explanation}
          </p>
          <p>
            <b>{t("ai.impact")}</b> {data.impact}
          </p>
          <p>
            <b>{t("ai.risk")}</b> {data.risk_explanation}
          </p>
          <p>
            <b>{t("ai.remediation")}</b> {data.remediation}
          </p>
        </div>
      )}
    </div>
  );
}