"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { authFetch } from "@/lib/api";
import { useAsk } from "@/lib/askContext";
import { useAuth } from "@/lib/auth";

const metrics = [
  { key: "total_jobs", label: "Total Jobs", hint: "Ingested pipeline", accent: "cyan", href: "/jobs" },
  {
    key: "shortlisted_jobs",
    label: "Shortlisted",
    hint: "Active pursuit",
    accent: "violet",
    href: "/shortlist",
  },
  {
    key: "applications_ready",
    label: "Packets Ready",
    hint: "Awaiting approval",
    accent: "amber",
    href: "/approvals",
  },
  {
    key: "submitted_applications",
    label: "Submitted",
    hint: "Human-approved sends",
    accent: "emerald",
    href: "/applications",
  },
] as const;

const quickActions = [
  { href: "/jobs", title: "Fresh Jobs", desc: "Browse, filter, and score the pipeline" },
  { href: "/opportunities/new", title: "New Opportunity", desc: "Ad-hoc intake from a URL or paste" },
  { href: "/approvals", title: "Approval Queue", desc: "Review packets before any external action" },
  { href: "/applications", title: "Applications", desc: "Download docs and record submission outcomes" },
  { href: "/gmail-reviews", title: "Gmail Review", desc: "Approve or reject ingested job alerts" },
  { href: "/settings", title: "Settings", desc: "Google OAuth, Drive root, and validation" },
];

export default function HomePage() {
  const { status } = useAuth();
  const { openAsk } = useAsk();
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
      <div className="page-header">
        <h1>Executive Overview</h1>
        <p>Loading command metrics…</p>
        <div className="grid metric-grid">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="metric-card skeleton-card" style={{ animationDelay: `${i * 80}ms` }} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      <header className="page-header">
        <div className="page-header-row">
          <div>
            <p className="eyebrow">Command center</p>
            <h1>Executive Overview</h1>
            <p>Local-first supervised career operations. Jump in below or ask the AI agent.</p>
          </div>
          <div className="header-actions">
            <div className="live-pill">
              <span className="live-dot" aria-hidden="true" />
              Live owner stack
            </div>
            <button type="button" className="secondary" onClick={() => openAsk()}>
              Ask Aarohan
            </button>
          </div>
        </div>
      </header>

      {error && (
        <div className="card warn">
          <p>{error}</p>
          <div className="actions">
            <button type="button" onClick={() => window.location.reload()}>
              Retry
            </button>
          </div>
        </div>
      )}

      <div className="grid metric-grid">
        {metrics.map(({ key, label, hint, accent, href }, index) => (
          <Link
            key={key}
            href={href}
            className={`metric-card metric-${accent} metric-link`}
            style={{ animationDelay: `${index * 70}ms` }}
          >
            <div className="metric-top">
              <span className="metric-label">{label}</span>
              <span className="metric-hint">{hint}</span>
            </div>
            <div className="metric-value">{analytics?.[key] ?? "—"}</div>
            <span className="metric-go">Open →</span>
          </Link>
        ))}
      </div>

      <section className="quick-actions-section">
        <h2>Quick actions</h2>
        <div className="grid quick-actions-grid">
          {quickActions.map((action) => (
            <Link key={action.href} href={action.href} className="quick-action-card">
              <strong>{action.title}</strong>
              <p>{action.desc}</p>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
