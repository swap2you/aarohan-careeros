"use client";

import { usePathname } from "next/navigation";

import { AskDrawer } from "@/components/AskDrawer";
import { EnvironmentBadge } from "@/components/EnvironmentBadge";
import { Nav } from "@/components/Nav";
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
      <div className="env-banner">
        <EnvironmentBadge />
      </div>
      <Nav />
      <main>{children}</main>
      <AskDrawer />
    </div>
  );
}

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <Shell>{children}</Shell>
    </AuthProvider>
  );
}
