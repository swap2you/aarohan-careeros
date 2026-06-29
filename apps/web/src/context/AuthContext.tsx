"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { API_BASE } from "@/lib/api";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

type SessionPayload = {
  authenticated: boolean;
  email?: string;
  user_id?: number;
  remember_me?: boolean;
  expires_at?: string;
};

type AuthContextValue = {
  status: AuthStatus;
  email: string | null;
  rememberMe: boolean;
  apiFetch: (path: string, init?: RequestInit) => Promise<Response>;
  login: (email: string, password: string, rememberMe: boolean, setup?: boolean) => Promise<void>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [email, setEmail] = useState<string | null>(null);
  const [rememberMe, setRememberMe] = useState(true);
  const [handlingExpiry, setHandlingExpiry] = useState(false);

  const clearClientAuth = useCallback(() => {
    setEmail(null);
    setStatus("unauthenticated");
    if (typeof window !== "undefined") {
      localStorage.removeItem("careeros_token");
    }
  }, []);

  const refreshSession = useCallback(async () => {
    const res = await fetch(`${API_BASE}/api/auth/session`, { credentials: "include", cache: "no-store" });
    if (!res.ok) {
      clearClientAuth();
      return;
    }
    const data = (await res.json()) as SessionPayload;
    if (data.authenticated && data.email) {
      setEmail(data.email);
      setRememberMe(Boolean(data.remember_me));
      setStatus("authenticated");
    } else {
      clearClientAuth();
    }
  }, [clearClientAuth]);

  useEffect(() => {
    refreshSession();
  }, [refreshSession]);

  const apiFetch = useCallback(
    async (path: string, init?: RequestInit) => {
      const response = await fetch(`${API_BASE}${path}`, {
        ...init,
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          ...(init?.headers || {}),
        },
        cache: "no-store",
      });
      if (response.status === 401 && !handlingExpiry) {
        setHandlingExpiry(true);
        clearClientAuth();
        const returnTo = encodeURIComponent(pathname || "/");
        router.replace(`/login?reason=session_expired&returnTo=${returnTo}`);
        setHandlingExpiry(false);
      }
      return response;
    },
    [clearClientAuth, handlingExpiry, pathname, router],
  );

  const login = useCallback(
    async (loginEmail: string, password: string, remember: boolean, setup = false) => {
      const endpoint = setup ? "/api/auth/setup" : "/api/auth/login";
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: loginEmail, password, remember_me: remember }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Authentication failed");
      }
      const data = (await res.json()) as SessionPayload;
      setEmail(data.email || loginEmail);
      setRememberMe(remember);
      setStatus("authenticated");
      const params = new URLSearchParams(window.location.search);
      const returnTo = params.get("returnTo") || "/";
      router.replace(returnTo.startsWith("/") ? returnTo : "/");
    },
    [router],
  );

  const logout = useCallback(async () => {
    await fetch(`${API_BASE}/api/auth/logout`, { method: "POST", credentials: "include" });
    clearClientAuth();
    router.replace("/login");
  }, [clearClientAuth, router]);

  const value = useMemo(
    () => ({ status, email, rememberMe, apiFetch, login, logout, refreshSession }),
    [status, email, rememberMe, apiFetch, login, logout, refreshSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
