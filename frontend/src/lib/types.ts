export interface User {
  id: number;
  username: string;
  email: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login_at?: string | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export type AssetKind = "ip" | "domain" | "hostname" | "docker";

export interface Asset {
  id: number;
  name: string;
  host: string;
  kind: AssetKind;
  docker_container?: string | null;
  description?: string | null;
  owner_id: number;
  created_at: string;
}

export type ScanType = "ping" | "tcp" | "quick";

export interface Scan {
  id: number;
  asset_id: number;
  created_by: number;
  status: string;
  scan_type: ScanType;
  ports?: string | null;
  command?: string | null;
  error?: string | null;
  risk_score?: number | null;
  risk_level?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface ScanResult extends Scan {
  result?: Record<string, unknown> | null;
}

export interface NmapScript {
  id: string;
  output: string;
  elements?: Record<string, string>;
}

export interface NmapPort {
  port: number;
  protocol: string;
  state: string;
  service: string;
  product: string;
  version: string;
  cpe: string;
  scripts?: NmapScript[];
}

export interface NmapOsMatch {
  name: string;
  accuracy: number;
  family: string;
}

export interface NmapHost {
  address: string;
  status: string;
  hostname: string;
  hostnames: { name: string; type: string }[];
  os_matches: NmapOsMatch[];
  status_reason?: string;
  uptime?: string;
  distance?: string;
  host_scripts?: NmapScript[];
  ports: NmapPort[];
}

export interface NmapScaninfo {
  type: string;
  protocol: string;
  num_services: number | null;
}

export interface NmapRun {
  command?: string;
  nmap_args?: string;
  nmap_version?: string;
  scaninfo?: NmapScaninfo;
  stats?: {
    elapsed?: number | null;
    hosts_up?: number;
    hosts_down?: number;
    hosts_total?: number;
  };
  hosts: NmapHost[];
}

/** GET /api/v1/scans/{id}/raw — архів сирого nmap-XML. */
export interface ScanRaw {
  scan_id: number;
  available: boolean;
  size_bytes: number;
  sha256: string;
  nmap_version: string;
  nmap_args: string;
  hosts_count: number;
  truncated: boolean;
  compressed: boolean;
  xml: string | null;
  parsed: NmapRun | null;
}

export interface Service {
  id: number;
  scan_id: number;
  host: string;
  port: number;
  protocol: string;
  state: string;
  service?: string | null;
  product?: string | null;
  version?: string | null;
  cpe?: string | null;
}

export interface ScanRisk {
  scan_id: number;
  risk_score: number;
  risk_level: string;
  services_count: number;
  findings_by_severity: Record<string, number>;
}

export interface Finding {
  id: number;
  scan_id: number;
  service_id?: number | null;
  severity: string;
  title: string;
  description?: string | null;
  recommendation?: string | null;
  cve?: string | null;
  created_at: string;
}

export interface AIExplanation {
  provider: string;
  explanation: string;
  impact: string;
  risk_explanation: string;
  remediation: string;
}

export type NotificationChannel = "web" | "email" | "telegram";
export type NotificationStatus = "sent" | "pending" | "failed" | "skipped";
export type NotifySeverity = "info" | "low" | "medium" | "high" | "critical";

export interface Notification {
  id: number;
  user_id: number;
  scan_id?: number | null;
  title: string;
  body?: string | null;
  severity?: string | null;
  is_read: boolean;
  created_at: string;
  channel: NotificationChannel;
  destination?: string | null;
  status: NotificationStatus;
  sent_at?: string | null;
  error?: string | null;
}

export interface NotificationPreferences {
  email_available: boolean;
  telegram_available: boolean;
  server_min_severity: NotifySeverity;
  effective_min_severity: NotifySeverity;
  email?: string | null;
  telegram_chat_id?: string | null;
  notify_email: boolean;
  notify_telegram: boolean;
  notify_min_severity: NotifySeverity;
}

export interface Report {
  id: number;
  title: string;
  report_type: string;
  created_by: number;
  asset_id?: number | null;
  scan_id?: number | null;
  created_at: string;
}

export interface ReportDetail extends Report {
  content: Record<string, unknown>;
}

export interface ScanBrief {
  id: number;
  asset_id: number;
  status: string;
  scan_type: string;
  risk_score?: number | null;
  risk_level?: string | null;
  created_at: string;
  finished_at?: string | null;
}

export interface DashboardStats {
  unread_notifications: number;
  total_assets: number;
  high_risk_scans: number;
  recent_scans: ScanBrief[];
}

export interface Health {
  status: string;
  services: Record<string, string>;
}