import "./globals.css";
import type { Metadata } from "next";
import { Suspense } from "react";

import { AppProviders } from "@/components/AppProviders";

export const metadata: Metadata = {
  title: "Aarohan CareerOS",
  description: "Supervised career operations dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Suspense fallback={<div className="auth-loading card">Loading…</div>}>
          <AppProviders>{children}</AppProviders>
        </Suspense>
      </body>
    </html>
  );
}
