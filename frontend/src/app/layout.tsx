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
      <body>
        <AuthProvider>
          <Nav />
          <main>{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}