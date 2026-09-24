"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth";

export default function HomePage() {
  const { session, ready } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (ready) router.replace(session ? "/dashboard" : "/login");
  }, [ready, session, router]);

  return <div className="empty">Перенаправлення…</div>;
}