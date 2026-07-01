"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { API_BASE } from "@/lib/api";

type SetupStatus = { setup_required: boolean; has_admin: boolean };
type BypassStatus = {
  enabled: boolean;
  auto_login: boolean;
  owner_email_hint: string | null;
};

export default function LoginPage() {
  const searchParams = useSearchParams();
  const autoLoginAttempted = useRef(false);
  const [setup, setSetup] = useState<SetupStatus | null>(null);
  const [bypass, setBypass] = useState<BypassStatus | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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
    fetch(`${API_BASE}/api/auth/local-bypass-status`)
      .then((res) => res.json())
      .then(setBypass)
      .catch(() => setBypass({ enabled: false, auto_login: false, owner_email_hint: null }));
  }, []);

  async function enterLocalAdmin() {
    setSubmitting(true);
    setError(null);
    const response = await fetch(`${API_BASE}/api/auth/local-admin-login`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ remember_me: rememberMe }),
    });
    setSubmitting(false);
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      setError(data.detail || "Local admin sign-in failed");
      return;
    }
    window.location.assign(returnTo.startsWith("/") ? returnTo : "/");
  }

  useEffect(() => {
    if (!bypass?.enabled || !bypass.auto_login || autoLoginAttempted.current || submitting) {
      return;
    }
    autoLoginAttempted.current = true;
    void enterLocalAdmin();
  }, [bypass, submitting]);

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

  function onEmailChange(value: string) {
    setEmail(value);
    if (error) {
      setError(null);
    }
  }

  const isSetup = setup?.setup_required;

  return (
    <div className="login-page">
      <div className="login card">
        <h1>{isSetup ? "First-run administrator setup" : "Sign in to Aarohan CareerOS"}</h1>
        {reason === "session_expired" && (
          <p className="warn">Your session expired. Sign in again to continue.</p>
        )}
        {bypass?.enabled && (
          <p className="muted">
            Local owner mode{bypass.owner_email_hint ? ` (${bypass.owner_email_hint})` : ""} — password
            sign-in or one-click local admin entry.
          </p>
        )}
        <label htmlFor="careeros-email">Email</label>
        <input
          id="careeros-email"
          value={email}
          onChange={(e) => onEmailChange(e.target.value)}
          autoComplete="username"
        />
        <label htmlFor="careeros-password">Password (min 12 characters)</label>
        <div className="password-field">
          <input
            id="careeros-password"
            type={showPassword ? "text" : "password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
          <button
            type="button"
            className="password-toggle"
            aria-label={showPassword ? "Hide password" : "Show password"}
            aria-pressed={showPassword}
            aria-controls="careeros-password"
            onClick={() => setShowPassword((visible) => !visible)}
          >
            {showPassword ? (
              <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <path
                  fill="currentColor"
                  d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"
                />
                <path fill="currentColor" d="M3.27 2.27 2 3.54l2.21 2.21C2.73 7.61 1 10.39 1 12c1.73 4.39 6 7.5 11 7.5 2.05 0 3.97-.5 5.66-1.37l2.04 2.04 1.27-1.27L3.27 2.27zm7.53 7.53-2.04-2.04A3.994 3.994 0 0 1 12 8c2.21 0 4 1.79 4 4 0 .74-.2 1.43-.55 2.02l-2.65-2.65A2.97 2.97 0 0 0 12 11c-1.66 0-3-1.34-3-3 0-.41.08-.8.23-1.15z" />
              </svg>
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <path
                  fill="currentColor"
                  d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"
                />
              </svg>
            )}
          </button>
        </div>
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={rememberMe}
            onChange={(e) => setRememberMe(e.target.checked)}
          />
          Remember me on this device
        </label>
        {error && <p className="error">{error}</p>}
        {bypass?.enabled && !isSetup && (
          <button type="button" className="secondary" disabled={submitting} onClick={() => void enterLocalAdmin()}>
            Enter Local Admin
          </button>
        )}
        <button type="button" disabled={submitting} onClick={() => submit(isSetup ? "/api/auth/setup" : "/api/auth/login")}>
          {isSetup ? "Create administrator" : "Sign in"}
        </button>
      </div>
    </div>
  );
}
