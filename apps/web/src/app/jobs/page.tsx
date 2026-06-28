"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

type Job = {
  id: number;
  title: string;
  company: string;
  state: string;
  selected?: boolean;
  score?: { total_score: number };
};

type WorkflowResult = { action: string; success: number; failed: number; details: unknown[] };

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [status, setStatus] = useState<string>("");
  const [forwardUrl, setForwardUrl] = useState("");
  const [profile, setProfile] = useState("qe_leadership");

  function token() {
    return localStorage.getItem("careeros_token") || "";
  }

  async function load() {
    const response = await fetch(`${API_BASE}/api/jobs`, {
      headers: { Authorization: `Bearer ${token()}` },
    });
    setJobs(await response.json());
  }

  useEffect(() => {
    load();
  }, []);

  async function runWorkflow(path: string, body?: unknown) {
    setStatus("Running...");
    const response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token()}`,
        "Content-Type": "application/json",
      },
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
        <button onClick={() => runWorkflow("/api/workflows/ingest/fixture")}>Import Fixture</button>
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
        <table>
          <thead>
            <tr><th></th><th>Title</th><th>Company</th><th>State</th><th>Score</th></tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id}>
                <td><input type="checkbox" checked={!!job.selected} onChange={() => toggleSelect(job.id)} /></td>
                <td>{job.title}</td>
                <td>{job.company}</td>
                <td>{job.state}</td>
                <td>{job.score?.total_score ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
