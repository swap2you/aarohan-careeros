"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { API_BASE, authFetch } from "@/lib/api";

type Application = {
  id: number;
  state: string;
  job_id: number;
  submitted_at?: string | null;
  packet_metadata?: {
    document_quality?: { passed?: boolean; template_version?: string };
    representation_risk?: { level?: string; summary?: string };
  };
};

type Version = {
  id: number;
  version_number: number;
  docx_path: string;
  pdf_path: string;
  is_submitted_immutable: boolean;
  created_at: string;
};

type TimelineEvent = {
  id: number;
  event_type: string;
  title: string;
  description: string;
  created_at: string;
};

type QualityReport = {
  passed: boolean;
  template_version?: string;
  ats_diagnostics?: { issues?: string[]; warnings?: string[] };
  answer_sheet?: string;
};

const STATE_LABELS: Record<string, string> = {
  DISCOVERED: "Discovered",
  SHORTLISTED: "Shortlisted",
  PACKET_GENERATING: "Generating packet",
  PACKET_READY: "Packet ready for review",
  NEEDS_EDIT: "Needs edits",
  APPROVED_FOR_SUBMISSION: "Approved — ready to apply",
  SUBMITTED: "Submitted (user confirmed)",
  REJECTED: "Rejected",
  SECONDARY_REVIEW: "On hold",
  CLOSED: "Closed",
};

function stateLabel(state: string) {
  return STATE_LABELS[state] || state.replace(/_/g, " ").toLowerCase();
}

export default function ApplicationsPage() {
  const [items, setItems] = useState<Application[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [quality, setQuality] = useState<QualityReport | null>(null);
  const [message, setMessage] = useState("");
  const [confirmSubmit, setConfirmSubmit] = useState(false);


  async function loadApplications() {
    const response = await authFetch(`/api/applications`);
    setItems(await response.json());
  }

  useEffect(() => {
    loadApplications();
  }, []);

  async function selectApplication(id: number) {
    setSelectedId(id);
    setMessage("");
    setConfirmSubmit(false);
    const [vRes, tRes, qRes] = await Promise.all([
      authFetch(`/api/applications/${id}/versions`),
      authFetch(`/api/applications/${id}/timeline`),
      authFetch(`/api/documents/applications/${id}/quality`),
    ]);
    setVersions(vRes.ok ? await vRes.json() : []);
    setTimeline(tRes.ok ? await tRes.json() : []);
    setQuality(qRes.ok ? await qRes.json() : null);
  }

  async function act(action: string, notes?: string) {
    if (!selectedId) return;
    const response = await authFetch(`/api/applications/${selectedId}/actions`, {
      method: "POST",
      body: JSON.stringify({ action, notes }),
    });
    const data = await response.json();
    if (!response.ok) {
      setMessage(typeof data.detail === "string" ? data.detail : "Action failed");
      return;
    }
    setMessage(`Recorded: ${stateLabel(data.state)}`);
    await loadApplications();
    await selectApplication(selectedId);
  }

  async function download(id: number, fileType: "docx" | "pdf") {
    const response = await authFetch(`/api/validation/applications/${id}/download/${fileType}`);
    if (!response.ok) return;
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `application_${id}.${fileType}`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const selected = items.find((i) => i.id === selectedId);

  return (
    <div>
      <h1>Applications</h1>
      <p>Review generated packets, approve or reject, and record manual submission outcomes.</p>

      <div className="card">
        {items.length === 0 ? (
          <p>No applications yet. Generate a packet from a job detail page.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Job</th>
                <th>Status</th>
                <th>Validation</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>{item.id}</td>
                  <td>
                    <Link href={`/jobs/${item.job_id}`}>Job #{item.job_id}</Link>
                  </td>
                  <td>{stateLabel(item.state)}</td>
                  <td>
                    {item.packet_metadata?.document_quality?.passed === false
                      ? "Failed validation"
                      : item.packet_metadata?.document_quality?.passed
                        ? "Passed"
                        : "—"}
                  </td>
                  <td>
                    <button type="button" onClick={() => selectApplication(item.id)}>
                      Review
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selected && (
        <div className="card">
          <h2>Application #{selected.id}</h2>
          <p>
            Status: <strong>{stateLabel(selected.state)}</strong>
            {selected.submitted_at && (
              <> · Submitted {new Date(selected.submitted_at).toLocaleString()}</>
            )}
          </p>
          <p>
            <Link href={`/jobs/${selected.job_id}`}>View job detail</Link> ·{" "}
            <Link href="/approvals">Approval queue</Link>
          </p>

          {quality && (
            <div className={quality.passed ? "risk-green" : "risk-red"}>
              <h3>Document validation: {quality.passed ? "Passed" : "Failed"}</h3>
              {quality.ats_diagnostics?.warnings?.map((w) => (
                <p key={w}>{w}</p>
              ))}
              {!quality.passed && (
                <p>Fix validation issues or regenerate before approval.</p>
              )}
            </div>
          )}

          <div className="actions">
            <button type="button" onClick={() => download(selected.id, "docx")}>
              Download DOCX
            </button>
            <button type="button" onClick={() => download(selected.id, "pdf")}>
              Download PDF
            </button>
            <button type="button" onClick={() => act("approve")}>
              Approve
            </button>
            <button type="button" onClick={() => act("reject")}>
              Reject
            </button>
            <button type="button" onClick={() => act("needs_edit")}>
              Needs edit
            </button>
            <button type="button" onClick={() => act("saved_for_later")}>
              Save for later
            </button>
            <button type="button" onClick={() => act("withdrawn")}>
              Withdraw
            </button>
          </div>

          <div className="actions">
            <button type="button" onClick={() => act("opened_application")}>
              Record: opened application
            </button>
            {!confirmSubmit ? (
              <button type="button" onClick={() => setConfirmSubmit(true)}>
                Mark submitted…
              </button>
            ) : (
              <>
                <p>
                  Confirm you submitted on the employer site. Aarohan did not submit automatically.
                </p>
                <button type="button" onClick={() => act("mark_submitted")}>
                  Yes, I submitted
                </button>
                <button type="button" onClick={() => act("not_submitted")}>
                  Not submitted
                </button>
                <button type="button" onClick={() => setConfirmSubmit(false)}>
                  Cancel
                </button>
              </>
            )}
          </div>

          {message && <p>{message}</p>}

          {versions.length > 0 && (
            <>
              <h3>Version history</h3>
              <ul>
                {versions.map((v) => (
                  <li key={v.id}>
                    v{v.version_number.toString().padStart(2, "0")} —{" "}
                    {v.is_submitted_immutable ? "Submitted (immutable)" : "Draft"} —{" "}
                    {new Date(v.created_at).toLocaleString()}
                  </li>
                ))}
              </ul>
            </>
          )}

          {timeline.length > 0 && (
            <>
              <h3>Timeline</h3>
              <ul>
                {timeline.map((ev) => (
                  <li key={ev.id}>
                    <strong>{ev.title}</strong> — {new Date(ev.created_at).toLocaleString()}
                    <br />
                    {ev.description}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}
