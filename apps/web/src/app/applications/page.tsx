"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { ToastStack } from "@/components/Toast";
import { authFetch } from "@/lib/api";
import { useToasts } from "@/lib/useToasts";

type Application = {
  id: number;
  state: string;
  job_id: number;
  job_title?: string | null;
  company_name?: string | null;
  official_url?: string | null;
  packet_version?: string | null;
  validation_status?: string;
  duplicate_risk?: string | null;
  generated_at?: string | null;
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

function validationLabel(status?: string) {
  if (status === "passed") return "Passed";
  if (status === "failed") return "Failed validation";
  return "Not validated";
}

function displayTitle(item: Application) {
  if (item.company_name && item.job_title) return `${item.company_name} — ${item.job_title}`;
  if (item.job_title) return item.job_title;
  return `Job #${item.job_id}`;
}

export default function ApplicationsPage() {
  const { toasts, push, dismiss } = useToasts();
  const [items, setItems] = useState<Application[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [total, setTotal] = useState(0);
  const [pageCount, setPageCount] = useState(1);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [quality, setQuality] = useState<QualityReport | null>(null);
  const [loadingList, setLoadingList] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [confirmReject, setConfirmReject] = useState(false);
  const [confirmSubmit, setConfirmSubmit] = useState(false);

  async function loadApplications(nextPage = page, nextSize = pageSize) {
    setLoadingList(true);
    try {
      const response = await authFetch(
        `/api/applications?page=${nextPage}&page_size=${nextSize}`,
      );
      if (!response.ok) {
        push("error", "Could not load applications.");
        return;
      }
      const data = await response.json();
      setItems(data.items || []);
      setPage(data.page || nextPage);
      setPageSize(data.page_size || nextSize);
      setTotal(data.total || 0);
      setPageCount(data.page_count || 1);
    } finally {
      setLoadingList(false);
    }
  }

  useEffect(() => {
    loadApplications();
  }, []);

  async function selectApplication(id: number) {
    setSelectedId(id);
    setConfirmReject(false);
    setConfirmSubmit(false);
    setLoadingDetail(true);
    try {
      const [vRes, tRes, qRes] = await Promise.all([
        authFetch(`/api/applications/${id}/versions`),
        authFetch(`/api/applications/${id}/timeline`),
        authFetch(`/api/documents/applications/${id}/quality`),
      ]);
      setVersions(vRes.ok ? await vRes.json() : []);
      setTimeline(tRes.ok ? await tRes.json() : []);
      setQuality(qRes.ok ? await qRes.json() : null);
    } finally {
      setLoadingDetail(false);
    }
  }

  async function act(action: string, notes?: string) {
    if (!selectedId) return;
    setActionLoading(action);
    try {
      const response = await authFetch(`/api/applications/${selectedId}/actions`, {
        method: "POST",
        body: JSON.stringify({ action, notes }),
      });
      const data = await response.json();
      if (!response.ok) {
        push("error", typeof data.detail === "string" ? data.detail : "Action failed");
        return;
      }
      push("success", `Status updated: ${stateLabel(data.state)}`);
      await loadApplications();
      await selectApplication(selectedId);
    } finally {
      setActionLoading(null);
      setConfirmReject(false);
      setConfirmSubmit(false);
    }
  }

  async function download(id: number, fileType: "docx" | "pdf") {
    setActionLoading(`download-${fileType}`);
    try {
      const response = await authFetch(`/api/validation/applications/${id}/download/${fileType}`);
      if (!response.ok) {
        push("error", `Could not download ${fileType.toUpperCase()}.`);
        return;
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `application_${id}.${fileType}`;
      a.click();
      URL.revokeObjectURL(url);
      push("success", `${fileType.toUpperCase()} download started.`);
    } finally {
      setActionLoading(null);
    }
  }

  const selected = items.find((i) => i.id === selectedId);
  const latestVersion = versions.length ? versions[versions.length - 1] : null;

  return (
    <div>
      <ToastStack toasts={toasts} onDismiss={dismiss} />
      <h1>Applications</h1>
      <p>Review generated packets, approve or reject, and record manual submission outcomes.</p>

      <div className="card">
        {loadingList ? (
          <p className="loading-inline">Loading applications…</p>
        ) : items.length === 0 ? (
          <p>No applications yet. Generate a packet from a job detail page.</p>
        ) : (
          <>
            <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Application</th>
                  <th>Status</th>
                  <th>Version</th>
                  <th>Validation</th>
                  <th>Duplicate risk</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <strong>{displayTitle(item)}</strong>
                      <br />
                      <span className="muted">{item.generated_at ? `Generated ${new Date(item.generated_at).toLocaleString()}` : "—"}</span>
                    </td>
                    <td>{stateLabel(item.state)}</td>
                    <td>{item.packet_version || "—"}</td>
                    <td>{validationLabel(item.validation_status)}</td>
                    <td>{item.duplicate_risk || "—"}</td>
                    <td>
                      <button type="button" onClick={() => selectApplication(item.id)}>
                        Review
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
            <div className="pagination">
              <span>
                {total} total · page {page} of {pageCount}
              </span>
              <label>
                Per page{" "}
                <select
                  value={pageSize}
                  onChange={(e) => {
                    const size = Number(e.target.value);
                    setPageSize(size);
                    loadApplications(1, size);
                  }}
                >
                  {[25, 50, 100].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
              <button type="button" disabled={page <= 1} onClick={() => loadApplications(page - 1)}>
                Previous
              </button>
              <button type="button" disabled={page >= pageCount} onClick={() => loadApplications(page + 1)}>
                Next
              </button>
            </div>
          </>
        )}
      </div>

      {selected && (
        <div className="card">
          {loadingDetail ? (
            <p className="loading-inline">Loading application details…</p>
          ) : (
            <>
              <h2>{displayTitle(selected)}</h2>
              <p>
                Status: <strong>{stateLabel(selected.state)}</strong>
                {selected.packet_version && <> · Packet {selected.packet_version}</>}
                {selected.generated_at && <> · Generated {new Date(selected.generated_at).toLocaleString()}</>}
                {selected.submitted_at && <> · Submitted {new Date(selected.submitted_at).toLocaleString()}</>}
              </p>
              <p className="muted">
                Duplicate risk: {selected.duplicate_risk || "—"} · Validation:{" "}
                {validationLabel(selected.validation_status)}
              </p>
              <p className="link-row">
                <Link href={`/jobs/${selected.job_id}`} className="inline-link">
                  View job detail
                </Link>
                <Link href="/approvals" className="inline-link">
                  Approval queue
                </Link>
                {selected.official_url && (
                  <a href={selected.official_url} target="_blank" rel="noreferrer" className="inline-link external">
                    Open official application ↗
                  </a>
                )}
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
                <button
                  type="button"
                  disabled={!!actionLoading}
                  onClick={() => download(selected.id, "docx")}
                >
                  {actionLoading === "download-docx" ? "Downloading…" : "Download DOCX"}
                </button>
                <button
                  type="button"
                  disabled={!!actionLoading}
                  onClick={() => download(selected.id, "pdf")}
                >
                  {actionLoading === "download-pdf" ? "Downloading…" : "Download PDF"}
                </button>
                <button type="button" disabled={!!actionLoading} onClick={() => act("approve")}>
                  {actionLoading === "approve" ? "Approving…" : "Approve"}
                </button>
                <button type="button" disabled={!!actionLoading} onClick={() => act("needs_edit")}>
                  {actionLoading === "needs_edit" ? "Saving…" : "Needs edit"}
                </button>
                <button type="button" disabled={!!actionLoading} onClick={() => act("hold")}>
                  {actionLoading === "hold" ? "Saving…" : "Hold"}
                </button>
                {!confirmReject ? (
                  <button type="button" disabled={!!actionLoading} onClick={() => setConfirmReject(true)}>
                    Reject…
                  </button>
                ) : (
                  <>
                    <p>Reject this application? This cannot be undone from the UI.</p>
                    <button type="button" disabled={!!actionLoading} onClick={() => act("reject")}>
                      {actionLoading === "reject" ? "Rejecting…" : "Confirm reject"}
                    </button>
                    <button type="button" onClick={() => setConfirmReject(false)}>
                      Cancel
                    </button>
                  </>
                )}
              </div>

              <div className="actions">
                <button type="button" disabled={!!actionLoading} onClick={() => act("opened_application")}>
                  {actionLoading === "opened_application" ? "Recording…" : "Record: opened application"}
                </button>
                {!confirmSubmit ? (
                  <button type="button" disabled={!!actionLoading} onClick={() => setConfirmSubmit(true)}>
                    Mark submitted…
                  </button>
                ) : (
                  <>
                    <p>
                      Confirm you submitted on the employer site using{" "}
                      <strong>{selected.packet_version || "current packet"}</strong>
                      {latestVersion && <> (resume v{latestVersion.version_number.toString().padStart(2, "0")})</>}.
                      Aarohan did not submit automatically.
                    </p>
                    {selected.official_url && (
                      <p>
                        Application URL:{" "}
                        <a href={selected.official_url} target="_blank" rel="noreferrer" className="inline-link external">
                          {selected.official_url.length > 64
                            ? `${selected.official_url.slice(0, 64)}…`
                            : selected.official_url}
                        </a>
                      </p>
                    )}
                    <button type="button" disabled={!!actionLoading} onClick={() => act("mark_submitted")}>
                      {actionLoading === "mark_submitted" ? "Recording…" : "Yes, I submitted"}
                    </button>
                    <button type="button" onClick={() => setConfirmSubmit(false)}>
                      Cancel
                    </button>
                  </>
                )}
              </div>

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
            </>
          )}
        </div>
      )}
    </div>
  );
}
