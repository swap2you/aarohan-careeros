"use client";

import { useEffect, useState } from "react";
import { authFetch } from "@/lib/api";

export default function AnalyticsPage() {
  const [data, setData] = useState<Record<string, number> | null>(null);
  const [budget, setBudget] = useState<{ status?: string; spent_usd?: number; cap_usd?: number } | null>(null);

  useEffect(() => {
    authFetch(`/api/analytics`).then((res) => res.json()).then(setData);
    authFetch(`/api/ai/budget`).then((res) => res.json()).then(setBudget);
  }, []);

  return (
    <div>
      <h1>Reports</h1>
      <div className="grid">
        <div className="card"><strong>Total jobs</strong><div>{data?.total_jobs ?? "—"}</div></div>
        <div className="card"><strong>Shortlisted</strong><div>{data?.shortlisted_jobs ?? "—"}</div></div>
        <div className="card"><strong>Packets ready</strong><div>{data?.applications_ready ?? "—"}</div></div>
        <div className="card"><strong>Submitted</strong><div>{data?.submitted_applications ?? "—"}</div></div>
        <div className="card"><strong>Interview packs</strong><div>{data?.interview_packs ?? "—"}</div></div>
        <div className="card"><strong>Consulting leads</strong><div>{data?.consulting_leads ?? "—"}</div></div>
      </div>
      {budget && (
        <div className="card">
          <h2>AI budget</h2>
          <p>Status: {budget.status ?? "unknown"}</p>
          {budget.spent_usd != null && <p>Spent: ${budget.spent_usd.toFixed(2)}</p>}
        </div>
      )}
    </div>
  );
}
