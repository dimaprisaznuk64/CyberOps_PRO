export function RiskPill({ risk }: { risk?: string | null }) {
  const level = (risk ?? "LOW").toLowerCase();
  return <span className={`pill ${level}`}>{(risk ?? "LOW").toUpperCase()}</span>;
}

export function SeverityPill({ severity }: { severity: string }) {
  return <span className={`pill ${severity.toLowerCase()}`}>{severity.toUpperCase()}</span>;
}

export function StatusPill({ status }: { status: string }) {
  const tone =
    status === "done"
      ? "ok"
      : status === "failed" || status === "cancelled"
        ? "critical"
        : status === "running"
          ? "medium"
          : "neutral";
  return <span className={`pill ${tone}`}>{status}</span>;
}