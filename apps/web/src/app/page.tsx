"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";

export default function HomePage() {
  const { apiFetch, status } = useAuth();
  const [analytics, setAnalytics] = useState<Record<string, number> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status !== "authenticated") return;
    apiFetch("/api/analytics")
      .then(async (res) => {
        if (!res.ok) throw new Error(`Failed to load analytics (${res.status})`);
        return res.json();
      })
      .then(setAnalytics)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load analytics"));
  }, [apiFetch, status]);

  if (status !== "authenticated") {
    return null;
  }

  return (
    <div>
      <h1>Executive Overview</h1>
      <p>Local-first supervised career operations. Schedules disabled by default.</p>
      {error && (
        <div className="card risk-amber">
          <p>{error}</p>
          <button type="button" onClick={() => window.location.reload()}>
            Retry
          </button>
        </div>
      )}
      <div className="grid">
        <div className="card">
          <strong>Total Jobs</strong>
          <div>{analytics?.total_jobs ?? "—"}</div>
        </div>
        <div className="card">
          <strong>Shortlisted</strong>
          <div>{analytics?.shortlisted_jobs ?? "—"}</div>
        </div>
        <div className="card">
          <strong>Packets Ready</strong>
          <div>{analytics?.applications_ready ?? "—"}</div>
        </div>
        <div className="card">
          <strong>Submitted</strong>
          <div>{analytics?.submitted_applications ?? "—"}</div>
        </div>
      </div>
    </div>
  );
}
