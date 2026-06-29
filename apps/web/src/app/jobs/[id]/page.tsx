"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";

type Risk = {
  level: "GREEN" | "AMBER" | "RED";
  indicator: string;
  summary: string;
  reasons: string[];
  can_override: boolean;
};

type JobDetail = {
  id: number;
  title: string;
  company: string;
  location: string | null;
  state: string;
  description_text: string;
  url: string;
  salary_min: number | null;
  salary_max: number | null;
  posted_at: string | null;
  source: string;
  score?: {
    total_score: number;
    trust_score: number | null;
    fit_reasons: string[] | null;
    trust_reasons: string[] | null;
    hard_filter_passed: boolean | null;
    hard_filter_reasons: string[] | null;
    match_card?: { summary?: string };
  };
};

function riskClass(level: string) {
  if (level === "RED") return "risk-red";
  if (level === "AMBER") return "risk-amber";
  return "risk-green";
}

export default function JobDetailPage() {
  const { apiFetch, status: authStatus } = useAuth();
  const params = useParams();
  const jobId = params?.id as string;
  const [job, setJob] = useState<JobDetail | null>(null);
  const [dupRisk, setDupRisk] = useState<Risk | null>(null);
  const [repRisk, setRepRisk] = useState<Risk | null>(null);
  const [applyReady, setApplyReady] = useState<{ can_open_apply: boolean; message: string } | null>(null);
  const [atsInfo, setAtsInfo] = useState<{ provider: string; summary: string; assisted_available: boolean } | null>(null);
  const [message, setMessage] = useState("");
  const [overrideReason, setOverrideReason] = useState("");

  const loadJobData = useCallback(async () => {
    if (!jobId) return;
    const [jobRes, dupRes, repRes, applyRes, atsRes] = await Promise.all([
      apiFetch(`/api/jobs/${jobId}`),
      apiFetch(`/api/companies/jobs/${jobId}/duplicate-risk`),
      apiFetch(`/api/representations/jobs/${jobId}/representation-risk`),
      apiFetch(`/api/applications/jobs/${jobId}/apply-readiness`),
      apiFetch(`/api/assisted-apply/jobs/${jobId}/ats-detection`),
    ]);
    if (jobRes.ok) setJob(await jobRes.json());
    if (dupRes.ok) setDupRisk(await dupRes.json());
    if (repRes.ok) setRepRisk(await repRes.json());
    if (applyRes.ok) setApplyReady(await applyRes.json());
    if (atsRes.ok) setAtsInfo(await atsRes.json());
  }, [apiFetch, jobId]);

  useEffect(() => {
    if (authStatus === "authenticated") void loadJobData();
  }, [authStatus, loadJobData]);

  async function generatePacket() {
    const res = await apiFetch(`/api/applications/jobs/${jobId}/generate`, { method: "POST" });
    const data = await res.json();
    setMessage(res.ok ? "Packet generated. Review it on the Applications page." : data.detail || "Generation failed");
  }

  async function recordOverride() {
    const res = await apiFetch(`/api/companies/jobs/${jobId}/duplicate-override`, {
      method: "POST",
      body: JSON.stringify({ reason: overrideReason }),
    });
    const data = await res.json();
    if (!res.ok) {
      setMessage(data.detail || "Override failed");
      return;
    }
    setMessage("Override recorded with audit trail.");
    const refreshed = await apiFetch(`/api/companies/jobs/${jobId}/duplicate-risk`);
    if (refreshed.ok) setDupRisk(await refreshed.json());
  }

  if (!job) return <p>Loading job detail…</p>;

  const salary =
    job.salary_min && job.salary_max
      ? `$${job.salary_min.toLocaleString()} – $${job.salary_max.toLocaleString()}`
      : "Not listed";

  return (
    <div>
      <p>
        <Link href="/jobs">← Back to jobs</Link>
      </p>
      <h1>{job.title}</h1>
      <p>
        {job.company} · {job.location ?? "Location TBD"} · {job.state}
      </p>
      <p>
        Salary: {salary} · Posted: {job.posted_at ? new Date(job.posted_at).toLocaleDateString() : "Unknown"} · Source:{" "}
        {job.source}
      </p>

      {dupRisk && (
        <div className={`card ${riskClass(dupRisk.level)}`}>
          <h3>Duplicate risk: {dupRisk.indicator}</h3>
          <p>{dupRisk.summary}</p>
          {dupRisk.reasons.length > 0 && (
            <ul>
              {dupRisk.reasons.map((r) => (
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
      )}

      {repRisk && repRisk.level !== "GREEN" && (
        <div className={`card ${riskClass(repRisk.level)}`}>
          <h3>Vendor / client: {repRisk.indicator}</h3>
          <p>{repRisk.summary}</p>
          {repRisk.reasons.length > 0 && (
            <ul>
              {repRisk.reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {job.score && (
        <div className="card">
          <h3>Fit & trust</h3>
          <p>Fit score: {Math.round(job.score.total_score)}</p>
          {job.score.trust_score != null && <p>Trust score: {Math.round(job.score.trust_score)}</p>}
          {job.score.hard_filter_passed === false && (
            <p className="risk-red">Hard filter failed: {(job.score.hard_filter_reasons || []).join("; ")}</p>
          )}
          {job.score.fit_reasons && job.score.fit_reasons.length > 0 && (
            <>
              <h4>Why this matches</h4>
              <ul>
                {job.score.fit_reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </>
          )}
          {job.score.trust_reasons && job.score.trust_reasons.length > 0 && (
            <>
              <h4>Trust signals</h4>
              <ul>
                {job.score.trust_reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      {atsInfo && (
        <div className="card">
          <h3>Application mode</h3>
          <p>
            ATS: {atsInfo.provider} — {atsInfo.summary}
          </p>
          {atsInfo.assisted_available ? (
            <p>
              Assisted mode can prepare fields for supported ATS pages and stops before employer Submit. Use the{" "}
              <Link href="/applications">Applications</Link> page after approving a packet.
            </p>
          ) : (
            <p>Use Manual mode: open the official employer URL only.</p>
          )}
        </div>
      )}

      <div className="card">
        <h3>Actions</h3>
        <button type="button" onClick={generatePacket}>
          Generate application packet
        </button>
        {applyReady && (
          <p>
            {applyReady.message}{" "}
            {applyReady.can_open_apply ? (
              <a href={job.url} target="_blank" rel="noreferrer">
                Open official application
              </a>
            ) : (
              <strong>Apply link blocked until conflicts are resolved.</strong>
            )}
          </p>
        )}
        {message && <p>{message}</p>}
      </div>

      <div className="card">
        <h3>Description</h3>
        <p style={{ whiteSpace: "pre-wrap" }}>{job.description_text.slice(0, 4000)}</p>
      </div>
    </div>
  );
}
