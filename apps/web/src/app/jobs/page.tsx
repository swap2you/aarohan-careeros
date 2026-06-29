"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { API_BASE, authFetch } from "@/lib/api";

type JobScore = {
  total_score: number;
  trust_score?: number;
  hard_filter_passed?: boolean;
  recommendation?: string;
  match_card?: { headline?: string; trust_highlights?: string[]; fit_highlights?: string[] };
};

type Job = {
  id: number;
  title: string;
  company: string;
  state: string;
  role_family?: string | null;
  is_expired?: boolean;
  source_verified?: boolean;
  match_summary?: string | null;
  selected?: boolean;
  score?: JobScore;
};

type WorkflowResult = { action: string; success: number; failed: number; details: unknown[] };

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState<string>("");
  const [forwardUrl, setForwardUrl] = useState("");
  const [profile, setProfile] = useState("qe_leadership");
  const devMode = process.env.NODE_ENV === "development" || process.env.NEXT_PUBLIC_E2E_MODE === "true";


  async function load() {
    const response = await authFetch(`/api/jobs?page=1&page_size=50`);
    const data = await response.json();
    setJobs(data.items || data);
    setTotal(data.total ?? (data.items || data).length);
  }

  useEffect(() => {
    load();
  }, []);

  async function runWorkflow(path: string, body?: unknown) {
    setStatus("Running...");
    const response = await authFetch(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    });
    const data: WorkflowResult = await response.json();
    setStatus(`${data.action}: success=${data.success}, failed=${data.failed}`);
    await load();
  }

  function toggleSelect(id: number) {
    setJobs((current) =>
      current.map((job) => (job.id === id ? { ...job, selected: !job.selected } : job)),
    );
  }

  async function generateSelected() {
    const ids = jobs.filter((j) => j.selected).map((j) => j.id);
    if (!ids.length) {
      setStatus("Select at least one job.");
      return;
    }
    await runWorkflow("/api/workflows/generate-packets", { job_ids: ids, resume_profile: profile });
  }

  return (
    <div>
      <h1>Fresh Jobs & Manual Workflows</h1>
      <div className="card actions">
        {devMode && (
          <button onClick={() => runWorkflow("/api/workflows/ingest/fixture")}>Import Fixture</button>
        )}
        <button onClick={() => runWorkflow("/api/workflows/ingest/public")}>Ingest Public Feed</button>
        <button onClick={() => runWorkflow("/api/workflows/score-all")}>Score All New Jobs</button>
        <button onClick={generateSelected}>Generate Selected Packets</button>
      </div>
      <div className="card">
        <label>Resume profile </label>
        <select value={profile} onChange={(e) => setProfile(e.target.value)}>
          <option value="qe_leadership">QE Leadership</option>
          <option value="platform_architect">Platform Architect</option>
          <option value="ai_enabled_qe">AI-Enabled QE</option>
        </select>
        <div style={{ marginTop: "1rem" }}>
          <input placeholder="Forwarded job URL" value={forwardUrl} onChange={(e) => setForwardUrl(e.target.value)} />
          <button onClick={() => runWorkflow("/api/workflows/import-url", { url: forwardUrl })}>Import URL</button>
        </div>
        {status && <p className="status">{status}</p>}
      </div>
      <div className="card">
        <p>{total} jobs (fixture/test data hidden in owner mode)</p>
        <table>
          <thead>
            <tr>
              <th></th>
              <th>Job</th>
              <th>Family</th>
              <th>Fit</th>
              <th>Trust</th>
              <th>Filter</th>
              <th>State</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id}>
                <td><input type="checkbox" checked={!!job.selected} onChange={() => toggleSelect(job.id)} /></td>
                <td>
                  <Link href={`/jobs/${job.id}`}>{job.title}</Link>
                  <br />
                  <small>{job.company}{job.is_expired ? " · expired" : ""}{job.source_verified ? " · verified source" : ""}</small>
                  {job.match_summary && <p><small>{job.match_summary}</small></p>}
                </td>
                <td>{job.role_family ?? "—"}</td>
                <td>{job.score?.total_score ?? "—"}</td>
                <td>{job.score?.trust_score ?? "—"}</td>
                <td>{job.score?.hard_filter_passed === false ? "FAIL" : job.score ? "PASS" : "—"}</td>
                <td>{job.state}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
