"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { session, ready } = useAuth();
  const { t } = useI18n();
  const router = useRouter();

  useEffect(() => {
    if (ready && !session) router.replace("/login");
  }, [ready, session, router]);

  if (!ready) return <div className="empty">{t("common.loading")}</div>;
  if (!session) return null;
  return <>{children}</>;
}