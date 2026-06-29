"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { API_BASE, authFetch, registerSessionExpiredHandler } from "@/lib/api";

export type AuthUser = { id: number; email: string };

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

type AuthContextValue = {
  status: AuthStatus;
  user: AuthUser | null;
  logout: () => Promise<void>;
  refreshSession: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const PUBLIC_PATHS = ["/login"];

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);

  const redirectToLogin = useCallback(
    (reason?: string) => {
      setUser(null);
      setStatus("unauthenticated");
      if (pathname === "/login") return;
      const returnTo = encodeURIComponent(pathname || "/");
      const query = reason ? `reason=${reason}&returnTo=${returnTo}` : `returnTo=${returnTo}`;
      router.replace(`/login?${query}`);
    },
    [pathname, router],
  );

  const refreshSession = useCallback(async () => {
    const response = await fetch(`${API_BASE}/api/auth/session`, {
      credentials: "include",
      cache: "no-store",
    });
    if (!response.ok) {
      redirectToLogin("session_expired");
      return;
    }
    const data = await response.json();
    if (!data.authenticated) {
      redirectToLogin(pathname === "/login" ? undefined : "session_expired");
      return;
    }
    setUser(data.user);
    setStatus("authenticated");
    if (pathname === "/login") {
      const returnTo = searchParams.get("returnTo") || "/";
      router.replace(returnTo.startsWith("/") ? returnTo : "/");
    }
  }, [pathname, redirectToLogin, router, searchParams]);

  useEffect(() => {
    registerSessionExpiredHandler(() => redirectToLogin("session_expired"));
  }, [redirectToLogin]);

  useEffect(() => {
    refreshSession();
  }, [refreshSession]);

  const logout = useCallback(async () => {
    await authFetch("/api/auth/logout", { method: "POST" });
    redirectToLogin();
  }, [redirectToLogin]);

  const value = useMemo(
    () => ({ status, user, logout, refreshSession }),
    [status, user, logout, refreshSession],
  );

  if (status === "loading" && !PUBLIC_PATHS.includes(pathname)) {
    return (
      <div className="auth-loading card">
        <h1>Checking session…</h1>
        <p>Verifying your sign-in before loading Aarohan CareerOS.</p>
      </div>
    );
  }

  if (status === "unauthenticated" && !PUBLIC_PATHS.includes(pathname)) {
    return (
      <div className="auth-loading card">
        <h1>Redirecting to sign in…</h1>
      </div>
    );
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
