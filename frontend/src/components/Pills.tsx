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

const CHANNEL_LABEL: Record<string, string> = {
  web: "WEB",
  email: "EMAIL",
  telegram: "TG",
};

const DELIVERY_TONE: Record<string, string> = {
  sent: "ok",
  pending: "medium",
  failed: "critical",
  skipped: "neutral",
};

export function ChannelPill({ channel }: { channel: string }) {
  return <span className="pill neutral">{CHANNEL_LABEL[channel] ?? channel}</span>;
}

export function DeliveryPill({ status }: { status: string }) {
  const tone = DELIVERY_TONE[status] ?? "neutral";
  const label = status === "skipped" ? "пропущено" : status;
  return <span className={`pill ${tone}`}>{label}</span>;
}