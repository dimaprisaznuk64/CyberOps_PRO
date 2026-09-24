export function StatCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: React.ReactNode;
  tone?: string;
}) {
  return (
    <div className="card">
      <b style={tone ? { color: tone } : undefined}>{value}</b>
      <span>{label}</span>
    </div>
  );
}