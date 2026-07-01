"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { ToastStack } from "@/components/Toast";
import { TtsMiniPlayer } from "@/components/TtsMiniPlayer";
import { authFetch } from "@/lib/api";
import { useToasts } from "@/lib/useToasts";

type Application = {
  id: number;
  job_id: number;
  state: string;
  job_title?: string | null;
  company_name?: string | null;
  official_url?: string | null;
  packet_version?: string | null;
  validation_status?: string;
  duplicate_risk?: string | null;
  generated_at?: string | null;
  cover_letter?: string;
  fit_analysis?: string;
  packet_metadata?: { preview_text?: string; missing_evidence_warnings?: string[] };
};

type PreviewPayload = Application & {
  resume_preview?: string;
};

const STATE_LABELS: Record<string, string> = {
  PACKET_READY: "Packet ready for review",
  NEEDS_EDIT: "Needs edits",
  APPROVED_FOR_SUBMISSION: "Approved — ready to apply",
};

function displayTitle(item: Application) {
  if (item.company_name && item.job_title) return `${item.company_name} — ${item.job_title}`;
  if (item.job_title) return item.job_title;
  return `Job #${item.job_id}`;
}

function validationLabel(status?: string) {
  if (status === "passed") return "Passed";
  if (status === "failed") return "Failed validation";
  return "Not validated";
}

export default function ApprovalsPage() {
  const { toasts, push, dismiss } = useToasts();
  const [items, setItems] = useState<Application[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [total, setTotal] = useState(0);
  const [pageCount, setPageCount] = useState(1);
  const [preview, setPreview] = useState<PreviewPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [confirmAction, setConfirmAction] = useState<{ id: number; action: string } | null>(null);

  async function load(nextPage = page, nextSize = pageSize) {
    setLoading(true);
    try {
      const response = await authFetch(`/api/applications/queue?page=${nextPage}&page_size=${nextSize}`);
      if (!response.ok) {
        push("error", "Could not load approval queue.");
        return;
      }
      const data = await response.json();
      setItems(data.items || []);
      setPage(data.page || nextPage);
      setPageSize(data.page_size || nextSize);
      setTotal(data.total || 0);
      setPageCount(data.page_count || 1);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function act(id: number, action: string) {
    setActionLoading(`${id}-${action}`);
    try {
      const response = await authFetch(`/api/applications/${id}/actions`, {
        method: "POST",
        body: JSON.stringify({ action }),
      });
      const data = await response.json();
      if (!response.ok) {
        push("error", typeof data.detail === "string" ? data.detail : "Action failed");
        return;
      }
      push("success", `Updated: ${STATE_LABELS[data.state] || data.state}`);
      setConfirmAction(null);
      await load();
    } finally {
      setActionLoading(null);
    }
  }

  async function showPreview(id: number) {
    setActionLoading(`${id}-preview`);
    try {
      const response = await authFetch(`/api/validation/applications/${id}/preview`);
      if (!response.ok) {
        push("error", "Could not load preview.");
        return;
      }
      setPreview(await response.json());
      push("info", "Preview loaded.");
    } finally {
      setActionLoading(null);
    }
  }

  async function download(id: number, fileType: "docx" | "pdf") {
    setActionLoading(`${id}-download-${fileType}`);
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

  function requestAction(id: number, action: string) {
    if (action === "reject" || action === "mark_submitted") {
      setConfirmAction({ id, action });
      return;
    }
    void act(id, action);
  }

  return (
    <div>
      <ToastStack toasts={toasts} onDismiss={dismiss} />
      <h1>Approval Queue</h1>
      <p>Packets awaiting review, edits, or submission confirmation.</p>

      <div className="card">
        {loading ? (
          <p className="loading-inline">Loading queue…</p>
        ) : items.length === 0 ? (
          <p>No items in queue.</p>
        ) : (
          <>
            {items.map((item) => (
              <div key={item.id} className="queue-item">
                <strong>{displayTitle(item)}</strong>
                <p className="muted">
                  {STATE_LABELS[item.state] || item.state} · {item.packet_version || "—"} ·{" "}
                  {validationLabel(item.validation_status)} · Duplicate: {item.duplicate_risk || "—"}
                  {item.generated_at && <> · Generated {new Date(item.generated_at).toLocaleString()}</>}
                </p>
                <div className="actions">
                  <button
                    type="button"
                    disabled={!!actionLoading}
                    onClick={() => showPreview(item.id)}
                  >
                    {actionLoading === `${item.id}-preview` ? "Loading…" : "Preview"}
                  </button>
                  <button
                    type="button"
                    disabled={!!actionLoading}
                    onClick={() => download(item.id, "docx")}
                  >
                    DOCX
                  </button>
                  <button
                    type="button"
                    disabled={!!actionLoading}
                    onClick={() => download(item.id, "pdf")}
                  >
                    PDF
                  </button>
                  <button
                    type="button"
                    disabled={!!actionLoading}
                    onClick={() => requestAction(item.id, "approve")}
                  >
                    Approve
                  </button>
                  <button
                    type="button"
                    disabled={!!actionLoading}
                    onClick={() => requestAction(item.id, "needs_edit")}
                  >
                    Needs Edit
                  </button>
                  <button type="button" disabled={!!actionLoading} onClick={() => requestAction(item.id, "hold")}>
                    Hold
                  </button>
                  <button type="button" disabled={!!actionLoading} onClick={() => requestAction(item.id, "reject")}>
                    Reject
                  </button>
                  {item.official_url && (
                    <a href={item.official_url} target="_blank" rel="noreferrer">
                      Open official application
                    </a>
                  )}
                  <button
                    type="button"
                    disabled={!!actionLoading}
                    onClick={() => requestAction(item.id, "mark_submitted")}
                  >
                    Mark Submitted
                  </button>
                  <Link href={`/applications`}>Full review</Link>
                </div>
              </div>
            ))}
            <div className="pagination">
              <span>
                {total} total · page {page} of {pageCount}
              </span>
              <button type="button" disabled={page <= 1} onClick={() => load(page - 1)}>
                Previous
              </button>
              <button type="button" disabled={page >= pageCount} onClick={() => load(page + 1)}>
                Next
              </button>
            </div>
          </>
        )}
      </div>

      {confirmAction && (
        <div className="card">
          <h3>Confirm {confirmAction.action.replace(/_/g, " ")}</h3>
          {confirmAction.action === "mark_submitted" && (
            <p>Aarohan did not submit automatically. Confirm you submitted on the employer site.</p>
          )}
          {confirmAction.action === "reject" && (
            <p>Reject this packet? You can regenerate from the job detail page later.</p>
          )}
          <div className="actions">
            <button
              type="button"
              disabled={!!actionLoading}
              onClick={() => act(confirmAction.id, confirmAction.action)}
            >
              Confirm
            </button>
            <button type="button" onClick={() => setConfirmAction(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {preview && (
        <div className="card">
          <h3>Packet Preview</h3>
          {preview.fit_analysis && <pre>{preview.fit_analysis}</pre>}
          {preview.cover_letter && (
            <>
              <pre>{preview.cover_letter}</pre>
              <TtsMiniPlayer text={preview.cover_letter} label="Cover letter" />
            </>
          )}
          {preview.resume_preview && <TtsMiniPlayer text={preview.resume_preview} label="Resume preview" />}
          {preview.packet_metadata?.preview_text && (
            <TtsMiniPlayer text={preview.packet_metadata.preview_text} label="Packet summary" />
          )}
          {preview.packet_metadata?.missing_evidence_warnings?.length ? (
            <div className="warn">
              <strong>Missing evidence warnings</strong>
              <ul>
                {preview.packet_metadata.missing_evidence_warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <button type="button" onClick={() => setPreview(null)}>
            Close preview
          </button>
        </div>
      )}
    </div>
  );
}
