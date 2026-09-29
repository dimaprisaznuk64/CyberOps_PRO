import type { Metadata } from "next";

import { Nav } from "@/components/Nav";
import { AuthProvider } from "@/lib/auth";

import "./globals.css";

export const metadata: Metadata = {
  title: "CyberOps PRO",
  description: "Uni banking cybersecurity platform dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="uk">
      <head>
        {/*
          Адреса API приходить окремим скриптом, а не вшивається в бандл:
          NEXT_PUBLIC_* фіксується під час `next build`, тож один образ
          ходив би у localhost браузера на будь-якому не-localhost стенді.
          Звичайний <script>, не next/script — значення має бути готове до
          гідратації, бо компоненти читають його під час першого рендеру.
        */}
        <script src="/runtime-config.js" />
      </head>
      <body>
        <AuthProvider>
          <Nav />
          <main>{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
