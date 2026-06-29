"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { authFetch } from "@/lib/api";

type Signal = {
  id: number;
  signal_type: string;
  original_classification?: string;
  sender: string | null;
  subject: string | null;
  snippet?: string | null;
  job_id: number | null;
  gmail_label?: string | null;
  classification_confidence?: number | null;
  received_at: string;
};

const CLASSIFICATIONS = [
  "JOB_ALERT",
  "RECRUITER_OUTREACH",
  "APPLICATION_CONFIRMATION",
  "ASSESSMENT",
  "INTERVIEW",
  "REJECTION",
  "OFFER",
  "FOLLOW_UP",
  "UNRELATED",
];

export default function RecruiterSignalsPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    const response = await authFetch(`/api/recruiter-signals`);
    setSignals(await response.json());
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function syncFixture() {
    setMessage("Syncing Gmail fixtures…");
    const response = await authFetch(`/api/integrations/gmail/sync-fixture`, { method: "POST" });
    const data = await response.json();
    if (!response.ok) {
      setMessage(data.detail || "Sync failed");
      return;
    }
    setMessage(
      `Processed ${data.processed ?? 0} messages · ${data.jobs_ingested ?? 0} new jobs · ${data.skipped ?? 0} skipped`,
    );
    await load();
  }

  async function syncLive() {
    setMessage("Syncing Gmail (read-only)…");
    const response = await authFetch(`/api/integrations/gmail/sync`, { method: "POST" });
    const data = await response.json();
    if (!response.ok) {
      setMessage(data.detail || "Sync failed");
      return;
    }
    setMessage(`Processed ${data.processed ?? 0} messages`);
    await load();
  }

  async function correct(id: number, classification: string) {
    const response = await authFetch(`/api/recruiter-signals/${id}/classification?classification=${classification}`, {
      method: "PATCH",
    });
    if (response.ok) await load();
  }

  return (
    <div>
      <h1>Gmail Lifecycle</h1>
      <p>Read-only Gmail sync, classification, and job-alert ingestion. No automatic replies.</p>
      <div className="actions">
        <button type="button" onClick={syncFixture}>
          Sync fixtures
        </button>
        <button type="button" onClick={syncLive}>
          Sync Gmail
        </button>
      </div>
      {message && <p className="status">{message}</p>}
      <div className="card">
        {signals.length === 0 ? (
          <p>No messages yet. Run fixture sync to load sample alerts.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Type</th>
                <th>Label</th>
                <th>Sender</th>
                <th>Subject</th>
                <th>Job</th>
                <th>Received</th>
                <th>Correct</th>
              </tr>
            </thead>
            <tbody>
              {signals.map((s) => (
                <tr key={s.id}>
                  <td>{s.signal_type}</td>
                  <td>{s.gmail_label ?? "—"}</td>
                  <td>{s.sender}</td>
                  <td>
                    <strong>{s.subject}</strong>
                    {s.snippet && <p><small>{s.snippet}</small></p>}
                  </td>
                  <td>{s.job_id ? <Link href={`/jobs/${s.job_id}`}>#{s.job_id}</Link> : "—"}</td>
                  <td>{new Date(s.received_at).toLocaleString()}</td>
                  <td>
                    <select
                      defaultValue=""
                      onChange={(e) => {
                        if (e.target.value) correct(s.id, e.target.value);
                      }}
                    >
                      <option value="">Reclassify…</option>
                      {CLASSIFICATIONS.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
