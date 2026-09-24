"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { session, ready } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (ready && !session) router.replace("/login");
  }, [ready, session, router]);

  if (!ready) return <div className="empty">Завантаження…</div>;
  if (!session) return null;
  return <>{children}</>;
}