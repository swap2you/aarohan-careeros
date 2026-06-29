"use client";

import { usePathname } from "next/navigation";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { Nav } from "@/components/Nav";

const PUBLIC_PATHS = ["/login"];

function ShellInner({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { status } = useAuth();
  const isPublic = PUBLIC_PATHS.includes(pathname);

  if (isPublic) {
    return <main className="auth-main">{children}</main>;
  }

  if (status === "loading") {
    return (
      <main className="auth-main">
        <div className="card auth-splash">
          <h1>Aarohan CareerOS</h1>
          <p>Checking your session…</p>
        </div>
      </main>
    );
  }

  if (status === "unauthenticated") {
    if (typeof window !== "undefined") {
      const returnTo = encodeURIComponent(pathname || "/");
      window.location.replace(`/login?returnTo=${returnTo}`);
    }
    return (
      <main className="auth-main">
        <div className="card auth-splash">
          <p>Redirecting to sign in…</p>
        </div>
      </main>
    );
  }

  return (
    <div className="layout">
      <Nav />
      <main>{children}</main>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <ShellInner>{children}</ShellInner>
    </AuthProvider>
  );
}
