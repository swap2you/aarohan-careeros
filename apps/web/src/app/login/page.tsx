"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

function LoginForm() {
  const { login, status } = useAuth();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [setupRequired, setSetupRequired] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const reason = searchParams.get("reason");

  useEffect(() => {
    if (status === "authenticated") {
      const returnTo = searchParams.get("returnTo") || "/";
      window.location.replace(returnTo.startsWith("/") ? returnTo : "/");
    }
  }, [status, searchParams]);

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000"}/api/auth/setup-status`)
      .then((r) => r.json())
      .then((data) => setSetupRequired(Boolean(data.setup_required)))
      .catch(() => setSetupRequired(false));
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password, rememberMe, setupRequired);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login card">
      <h1>{setupRequired ? "First-run administrator setup" : "Sign in to Aarohan"}</h1>
      {reason === "session_expired" && (
        <p className="warn">Your session expired. Sign in again to continue.</p>
      )}
      <form onSubmit={onSubmit}>
        <label htmlFor="login-email">Email</label>
        <input
          id="login-email"
          type="email"
          autoComplete="username"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <label htmlFor="login-password">Password (min 12 characters)</label>
        <input
          id="login-password"
          type="password"
          autoComplete={setupRequired ? "new-password" : "current-password"}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={12}
        />
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={rememberMe}
            onChange={(e) => setRememberMe(e.target.checked)}
          />
          Remember me on this device
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={submitting}>
          {setupRequired ? "Create administrator" : "Sign in"}
        </button>
      </form>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="card auth-splash">Loading…</div>}>
      <LoginForm />
    </Suspense>
  );
}
