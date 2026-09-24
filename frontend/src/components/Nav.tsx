"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/lib/auth";

const LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/assets", label: "Assets" },
  { href: "/scans", label: "Scans" },
  { href: "/findings", label: "Findings" },
  { href: "/reports", label: "Reports" },
  { href: "/notifications", label: "Notifications" },
  { href: "/settings", label: "Settings" },
];

export function Nav() {
  const { session, logout } = useAuth();
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
            {l.label}
          </Link>
        ))}
      </nav>
      {session && (
        <>
          <span className="user">
            {session.username} · <span className="pill neutral">{session.role}</span>
          </span>
          <button className="ghost sm" onClick={logout}>
            Logout
          </button>
        </>
      )}
    </header>
  );
}