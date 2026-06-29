"use client";

import { useEffect, useState } from "react";

import { authFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function HomePage() {
  const { status } = useAuth();
  const [analytics, setAnalytics] = useState<Record<string, number> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (status !== "authenticated") return;
    setLoading(true);
    authFetch("/api/analytics")
      .then(async (res) => {
        if (!res.ok) throw new Error("Failed to load analytics");
        return res.json();
      })
      .then(setAnalytics)
      .catch(() => setError("Could not load dashboard metrics. Retry in a moment."))
      .finally(() => setLoading(false));
  }, [status]);

  if (status === "loading" || loading) {
    return (
      <div className="card">
        <h1>Executive Overview</h1>
        <p>Loading dashboard…</p>
      </div>
    );
  }

  return (
    <div>
      <h1>Executive Overview</h1>
      <p>Local-first supervised career operations. Schedules disabled by default.</p>
      {error && (
        <div className="card warn">
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
