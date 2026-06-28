"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { API_BASE } from "@/lib/api";

type DuplicateRisk = {
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
  score?: {
    total_score: number;
    compensation_score: number;
    remote_score: number;
    technical_fit_score: number;
    fit_analysis: string | null;
    gap_analysis: string | null;
  };
};

function riskClass(level: string) {
  if (level === "RED") return "risk-red";
  if (level === "AMBER") return "risk-amber";
  return "risk-green";
}

export default function JobDetailPage() {
  const params = useParams();
  const jobId = params?.id as string;
  const [job, setJob] = useState<JobDetail | null>(null);
  const [risk, setRisk] = useState<DuplicateRisk | null>(null);
  const [overrideReason, setOverrideReason] = useState("");
  const [message, setMessage] = useState("");

  function token() {
    return localStorage.getItem("careeros_token") || "";
  }

  useEffect(() => {
    if (!jobId) return;
    const headers = { Authorization: `Bearer ${token()}` };
    fetch(`${API_BASE}/api/jobs/${jobId}`, { headers })
      .then((res) => res.json())
      .then(setJob);
    fetch(`${API_BASE}/api/companies/jobs/${jobId}/duplicate-risk`, { headers })
      .then((res) => res.json())
      .then(setRisk);
  }, [jobId]);

  async function recordOverride() {
    const response = await fetch(`${API_BASE}/api/companies/jobs/${jobId}/duplicate-override`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token()}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ reason: overrideReason }),
    });
    const data = await response.json();
    if (!response.ok) {
      setMessage(data.detail || "Override failed");
      return;
    }
    setMessage("Override recorded with audit trail.");
    const refreshed = await fetch(`${API_BASE}/api/companies/jobs/${jobId}/duplicate-risk`, {
      headers: { Authorization: `Bearer ${token()}` },
    });
    setRisk(await refreshed.json());
  }

  if (!job) return <p>Loading job detail...</p>;

  return (
    <div>
      <h1>{job.title}</h1>
      <p>
        {job.company} · {job.location ?? "Location TBD"} · {job.state}
      </p>
      {risk && (
        <div className={`card ${riskClass(risk.level)}`}>
          <h3>Duplicate risk: {risk.indicator}</h3>
          <p>{risk.summary}</p>
          {risk.reasons.length > 0 && (
            <ul>
              {risk.reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          )}
          {risk.can_override && risk.level === "RED" && (
            <div>
              <p>Record an override with reason to proceed (audit logged):</p>
              <textarea
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                rows={3}
                placeholder="Minimum 10 characters"
              />
              <button type="button" onClick={recordOverride} disabled={overrideReason.length < 10}>
                Record override
              </button>
            </div>
          )}
          {message && <p>{message}</p>}
        </div>
      )}
      <div className="card">
        <h3>Score</h3>
        <p>Total: {job.score?.total_score ?? "—"}</p>
        <pre>{JSON.stringify(job.score, null, 2)}</pre>
      </div>
      <div className="card">
        <h3>Description</h3>
        <pre>{job.description_text}</pre>
      </div>
      <div className="card">
        <a href={job.url} target="_blank" rel="noreferrer">
          View posting
        </a>
      </div>
    </div>
  );
}
