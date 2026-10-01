"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export default function HomePage() {
  const { session, ready } = useAuth();
  const { t } = useI18n();
  const router = useRouter();

  useEffect(() => {
    if (ready) router.replace(session ? "/dashboard" : "/login");
  }, [ready, session, router]);

  return <div className="empty">{t("home.redirecting")}</div>;
}