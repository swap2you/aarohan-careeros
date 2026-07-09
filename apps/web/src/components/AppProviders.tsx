"use client";

import { usePathname } from "next/navigation";

import { EnvironmentBadge } from "@/components/EnvironmentBadge";
import { Nav } from "@/components/Nav";
import { AskProvider } from "@/lib/askContext";
import { AuthProvider, useAuth } from "@/lib/auth";

function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { status } = useAuth();

  if (pathname === "/login") {
    return <>{children}</>;
  }

  if (status !== "authenticated") {
    return null;
  }

  return (
    <div className="layout">
      <header className="top-bar">
        <EnvironmentBadge />
      </header>
      <Nav />
      <main className="main-content">
        <div className="main-inner page-enter">{children}</div>
      </main>
    </div>
  );
}

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <AskProvider>
        <Shell>{children}</Shell>
      </AskProvider>
    </AuthProvider>
  );
}
