"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { API_BASE } from "@/lib/api";

type SetupStatus = { setup_required: boolean; has_admin: boolean };

export default function LoginPage() {
  const searchParams = useSearchParams();
  const [setup, setSetup] = useState<SetupStatus | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const reason = searchParams.get("reason");
  const returnTo = searchParams.get("returnTo") || "/";

  useEffect(() => {
    fetch(`${API_BASE}/api/auth/setup-status`)
      .then((res) => res.json())
      .then(setSetup)
      .catch(() => setSetup({ setup_required: true, has_admin: false }));
  }, []);

  async function submit(path: "/api/auth/setup" | "/api/auth/login") {
    setSubmitting(true);
    setError(null);
    const response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, remember_me: rememberMe }),
    });
    setSubmitting(false);
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      setError(data.detail || "Authentication failed");
      return;
    }
    window.location.assign(returnTo.startsWith("/") ? returnTo : "/");
  }

  const isSetup = setup?.setup_required;

  return (
    <div className="login-page">
      <div className="login card">
        <h1>{isSetup ? "First-run administrator setup" : "Sign in to Aarohan CareerOS"}</h1>
        {reason === "session_expired" && (
          <p className="warn">Your session expired. Sign in again to continue.</p>
        )}
        <label htmlFor="careeros-email">Email</label>
        <input id="careeros-email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
        <label htmlFor="careeros-password">Password (min 12 characters)</label>
        <input
          id="careeros-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
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
        <button type="button" disabled={submitting} onClick={() => submit(isSetup ? "/api/auth/setup" : "/api/auth/login")}>
          {isSetup ? "Create administrator" : "Sign in"}
        </button>
      </div>
    </div>
  );
}
