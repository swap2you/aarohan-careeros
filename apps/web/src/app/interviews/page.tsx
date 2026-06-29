"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { authFetch } from "@/lib/api";

type Pack = {
  id: number;
  job_id: number;
  company_briefing?: string;
  role_map?: string;
  questions?: Record<string, string[]>;
  star_stories?: Record<string, string>;
  interview_rounds?: { rounds: Array<{ name: string; focus: string; status: string }> };
  negotiation_prep?: { research?: string[]; questions_for_them?: string[]; boundaries?: string };
  document_links?: Record<string, unknown>;
  recruiter_timeline?: Array<{ signal_type: string; subject?: string; snippet?: string }>;
  gaps_and_risks?: { verified_strengths?: string[]; risks?: string[] };
};

export default function InterviewsPage() {
  const [jobId, setJobId] = useState("1");
  const [pack, setPack] = useState<Pack | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    authFetch(`/api/interviews/${jobId}`)
      .then((res) => (res.ok ? res.json() : null))
      .then(setPack);
  }, [jobId]);

  async function generate() {
    setMessage("Generating interview pack…");
    const response = await authFetch(`/api/interviews/jobs/${jobId}/generate`, { method: "POST" });
    const data = await response.json();
    if (!response.ok) {
      setMessage(data.detail || "Generation failed");
      return;
    }
    setPack(data);
    setMessage("Interview pack ready.");
  }

  return (
    <div>
      <h1>Interview Preparation</h1>
      <p>Evidence-grounded prep from approved Career Vault items only.</p>
      <label htmlFor="job-id">Job ID</label>
      <input id="job-id" value={jobId} onChange={(e) => setJobId(e.target.value)} />
      <div className="actions">
        <button type="button" onClick={generate}>Generate pack</button>
        {pack && <Link href={`/jobs/${jobId}`}>View job</Link>}
      </div>
      {message && <p className="status">{message}</p>}

      {pack && (
        <>
          <div className="card">
            <h2>Company brief</h2>
            <p>{pack.company_briefing}</p>
            <p><small>{pack.role_map}</small></p>
          </div>

          {pack.interview_rounds?.rounds && (
            <div className="card">
              <h2>Interview rounds</h2>
              <ul>
                {pack.interview_rounds.rounds.map((r) => (
                  <li key={r.name}><strong>{r.name}</strong> — {r.focus} ({r.status})</li>
                ))}
              </ul>
            </div>
          )}

          {pack.star_stories && (
            <div className="card">
              <h2>STAR stories (approved evidence)</h2>
              <ul>
                {Object.entries(pack.star_stories).map(([k, v]) => (
                  <li key={k}><strong>{k}</strong>: {v}</li>
                ))}
              </ul>
            </div>
          )}

          {pack.questions && (
            <div className="card">
              <h2>Likely questions</h2>
              {Object.entries(pack.questions).map(([stage, qs]) => (
                <div key={stage}>
                  <h3>{stage.replace(/_/g, " ")}</h3>
                  <ul>{qs.map((q) => <li key={q}>{q}</li>)}</ul>
                </div>
              ))}
            </div>
          )}

          {pack.negotiation_prep && (
            <div className="card">
              <h2>Compensation & negotiation</h2>
              <ul>{pack.negotiation_prep.research?.map((r) => <li key={r}>{r}</li>)}</ul>
              <p><em>{pack.negotiation_prep.boundaries}</em></p>
            </div>
          )}

          {pack.document_links && (
            <div className="card">
              <h2>Submitted documents</h2>
              <pre>{JSON.stringify(pack.document_links, null, 2)}</pre>
            </div>
          )}
        </>
      )}
    </div>
  );
}
