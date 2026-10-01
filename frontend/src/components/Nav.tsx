"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useAuth } from "@/lib/auth";
import { useI18n, type TKey } from "@/lib/i18n";

const LINKS: Array<{ href: string; key: TKey }> = [
  { href: "/dashboard", key: "nav.dashboard" },
  { href: "/assets", key: "nav.assets" },
  { href: "/scans", key: "nav.scans" },
  { href: "/findings", key: "nav.findings" },
  { href: "/reports", key: "nav.reports" },
  { href: "/notifications", key: "nav.notifications" },
  { href: "/settings", key: "nav.settings" },
];

export function Nav() {
  const { session, logout } = useAuth();
  const { t } = useI18n();
  const pathname = usePathname();

  return (
    <header className="topbar">
      <h1>🛡 CyberOps</h1>
      <nav>
        {LINKS.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className={
              pathname === l.href || pathname.startsWith(l.href + "/") ? "active" : undefined
            }
          >
            {t(l.key)}
          </Link>
        ))}
      </nav>
      <LanguageSwitcher />
      {session && (
        <>
          <span className="user">
            {session.username} · <span className="pill neutral">{session.role}</span>
          </span>
          <button className="ghost sm" onClick={logout}>
            {t("nav.logout")}
          </button>
        </>
      )}
    </header>
  );
}