"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

type SetupStatus = { setup_required: boolean; has_admin: boolean };

export default function HomePage() {
  const [token, setToken] = useState<string | null>(null);
  const [setup, setSetup] = useState<SetupStatus | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [analytics, setAnalytics] = useState<Record<string, number> | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem("careeros_token");
    if (saved) setToken(saved);
    fetch(`${API_BASE}/api/auth/setup-status`)
      .then((res) => res.json())
      .then(setSetup)
      .catch(() => setSetup({ setup_required: true, has_admin: false }));
  }, []);

  useEffect(() => {
    if (!token) return;
    fetch(`${API_BASE}/api/analytics`, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => res.json())
      .then(setAnalytics)
      .catch(() => setError("Failed to load analytics"));
  }, [token]);

  async function submitAuth(path: "/api/auth/setup" | "/api/auth/login") {
    setError(null);
    const response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      setError(data.detail || "Authentication failed");
      return;
    }
    const data = await response.json();
    localStorage.setItem("careeros_token", data.access_token);
    setToken(data.access_token);
  }

  if (!token) {
    const isSetup = setup?.setup_required;
    return (
      <div className="login card">
        <h1>{isSetup ? "First-run administrator setup" : "Sign in"}</h1>
        <label>Email</label>
        <input value={email} onChange={(e) => setEmail(e.target.value)} />
        <label>Password (min 12 characters)</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        {error && <p className="error">{error}</p>}
        <button onClick={() => submitAuth(isSetup ? "/api/auth/setup" : "/api/auth/login")}>
          {isSetup ? "Create administrator" : "Login"}
        </button>
      </div>
    );
  }

  return (
    <div>
      <h1>Executive Overview</h1>
      <p>Local-first supervised career operations. Schedules disabled by default.</p>
      <div className="grid">
        <div className="card"><strong>Total Jobs</strong><div>{analytics?.total_jobs ?? "—"}</div></div>
        <div className="card"><strong>Shortlisted</strong><div>{analytics?.shortlisted_jobs ?? "—"}</div></div>
        <div className="card"><strong>Packets Ready</strong><div>{analytics?.applications_ready ?? "—"}</div></div>
        <div className="card"><strong>Submitted</strong><div>{analytics?.submitted_applications ?? "—"}</div></div>
      </div>
    </div>
  );
}
