"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { RouteErrorPanel } from "@/components/RouteErrorPanel";
import { authFetch } from "@/lib/api";

type Risk = {
  level: string;
  indicator: string;
  summary: string;
  reasons?: string[];
  can_override?: boolean;
};

type JobDetailPayload = {
  job: {
    id: number;
    title: string;
    company: string;
    location: string | null;
    workplace_type: string | null;
    state: string;
    source: string;
    url: string;
    salary_min: number | null;
    salary_max: number | null;
    posted_at: string | null;
    age_days: number | null;
    description_text: string;
    is_expired: boolean;
  };
  score: {
    total_score: number;
    trust_score: number | null;
    fit_reasons: string[];
    trust_reasons: string[];
    hard_filter_passed: boolean | null;
    hard_filter_reasons: string[];
  } | null;
  duplicate_risk: Risk;
  representation_risk: Risk;
  apply_readiness: { can_open_apply: boolean; message: string; official_url: string };
  ats: { provider: string; summary: string; assisted_available: boolean };
  application: {
    id: number;
    state: string;
    validation_passed?: boolean;
    drive_links?: Record<string, string>;
    latest_version?: number;
  } | null;
};

function riskClass(level: string) {
  if (level === "RED") return "risk-red";
  if (level === "AMBER") return "risk-amber";
  return "risk-green";
}

function formatSalary(min: number | null, max: number | null): string {
  if (min && max) return `$${min.toLocaleString()} – $${max.toLocaleString()}`;
  if (min) return `From $${min.toLocaleString()}`;
  if (max) return `Up to $${max.toLocaleString()}`;
  return "Not listed";
}

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params?.id as string;
  const [detail, setDetail] = useState<JobDetailPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [overrideReason, setOverrideReason] = useState("");

  const load = useCallback(async () => {
    if (!jobId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await authFetch(`/api/jobs/${jobId}/detail`);
      if (response.status === 404) {
        setError("This job was not found. It may have been removed.");
        setDetail(null);
        return;
      }
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        setError(typeof data.detail === "string" ? data.detail : "Could not load job details.");
        setDetail(null);
        return;
      }
      setDetail(await response.json());
    } catch {
      setError("Network error while loading job details.");
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    load();
  }, [load]);

  async function generatePacket() {
    const res = await authFetch(`/api/applications/jobs/${jobId}/generate`, { method: "POST" });
    const data = await res.json();
    setMessage(
      res.ok ? "Packet generated. Review it on the Applications page." : data.detail || "Generation failed",
    );
    if (res.ok) await load();
  }

  async function recordOverride() {
    const res = await authFetch(`/api/companies/jobs/${jobId}/duplicate-override`, {
      method: "POST",
      body: JSON.stringify({ reason: overrideReason }),
    });
    const data = await res.json();
    if (!res.ok) {
      setMessage(data.detail || "Override failed");
      return;
    }
    setMessage("Override recorded with audit trail.");
    await load();
  }

  if (loading) return <p className="loading-skeleton">Loading job details…</p>;

  if (error || !detail) {
    return (
      <RouteErrorPanel
        title="Job detail unavailable"
        message={error || "Unable to display this job."}
        onRetry={load}
        backHref="/jobs"
        backLabel="Back to Jobs"
      />
    );
  }

  const { job, score, duplicate_risk: dupRisk, representation_risk: repRisk, apply_readiness: applyReady, ats, application } =
    detail;
  const reasons = (risk: Risk) => (Array.isArray(risk.reasons) ? risk.reasons : []);
  const description = job.description_text?.trim() || "No description available for this listing.";

  return (
    <div>
      <p>
        <Link href="/jobs">← Back to jobs</Link>
      </p>
      <h1>{job.title}</h1>
      <p>
        {job.company} · {job.location || "Location TBD"} · {job.workplace_type || "Workplace TBD"} · {job.state}
      </p>
      <p>
        Salary: {formatSalary(job.salary_min, job.salary_max)} · Posted:{" "}
        {job.posted_at ? new Date(job.posted_at).toLocaleDateString() : "Unknown"}
        {job.age_days != null ? ` (${job.age_days}d ago)` : ""} · Source: {job.source}
        {job.is_expired ? " · Expired" : ""}
      </p>

      <div className={`card ${riskClass(dupRisk.level)}`}>
        <h3>Duplicate risk: {dupRisk.indicator}</h3>
        <p>{dupRisk.summary}</p>
        {reasons(dupRisk).length > 0 && (
          <ul>
            {reasons(dupRisk).map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        )}
        {dupRisk.can_override && dupRisk.level === "RED" && (
          <div>
            <p>Record an override with reason (audit logged):</p>
            <textarea value={overrideReason} onChange={(e) => setOverrideReason(e.target.value)} rows={3} />
            <button type="button" onClick={recordOverride} disabled={overrideReason.length < 10}>
              Record override
            </button>
          </div>
        )}
      </div>

      {repRisk.level !== "GREEN" && (
        <div className={`card ${riskClass(repRisk.level)}`}>
          <h3>Vendor / client: {repRisk.indicator}</h3>
          <p>{repRisk.summary}</p>
          {reasons(repRisk).length > 0 && (
            <ul>
              {reasons(repRisk).map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {score && (
        <div className="card">
          <h3>Fit & trust</h3>
          <p>Fit score: {Math.round(score.total_score)}</p>
          {score.trust_score != null && <p>Trust score: {Math.round(score.trust_score)}</p>}
          {score.hard_filter_passed === false && (
            <p className="risk-red">Hard filter failed: {(score.hard_filter_reasons || []).join("; ")}</p>
          )}
          {(score.fit_reasons || []).length > 0 && (
            <>
              <h4>Why this matches</h4>
              <ul>
                {score.fit_reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </>
          )}
          {(score.trust_reasons || []).length > 0 && (
            <>
              <h4>Trust signals</h4>
              <ul>
                {score.trust_reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      {application && (
        <div className="card">
          <h3>Application status</h3>
          <p>
            Status: {application.state.replace(/_/g, " ")} · Version v
            {(application.latest_version ?? 1).toString().padStart(2, "0")}
          </p>
          <p>
            Validation: {application.validation_passed === false ? "Failed" : application.validation_passed ? "Passed" : "—"}
          </p>
          <Link href="/applications">Open applications</Link>
        </div>
      )}

      <div className="card">
        <h3>Application mode</h3>
        <p>
          ATS: {ats.provider} — {ats.summary}
        </p>
      </div>

      <div className="card">
        <h3>Actions</h3>
        <button type="button" onClick={generatePacket}>
          Generate application packet
        </button>
        <p>
          {applyReady.message}{" "}
          {applyReady.can_open_apply && job.url ? (
            <a href={job.url} target="_blank" rel="noreferrer">
              Open official application
            </a>
          ) : (
            <strong>Apply link blocked until conflicts are resolved.</strong>
          )}
        </p>
        {message && <p className="status">{message}</p>}
      </div>

      <div className="card">
        <h3>Description</h3>
        <p style={{ whiteSpace: "pre-wrap" }}>{description.slice(0, 8000)}</p>
      </div>
    </div>
  );
}
