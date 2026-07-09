"use client";

import { useEffect, useState } from "react";

import { ToastStack } from "@/components/Toast";
import { authFetch } from "@/lib/api";
import { useToasts } from "@/lib/useToasts";

type ReviewItem = {
  id: number;
  status: string;
  gmail_label?: string | null;
  sender?: string | null;
  subject?: string | null;
  snippet?: string | null;
  confidence?: number | null;
  ignored_reason?: string | null;
  job_id?: number | null;
  created_at?: string | null;
};

export default function GmailReviewsPage() {
  const { toasts, push, dismiss } = useToasts();
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [total, setTotal] = useState(0);
  const [pageCount, setPageCount] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  async function load(nextPage = page, filter = statusFilter) {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(nextPage),
        page_size: String(pageSize),
      });
      if (filter) params.set("status", filter);
      const response = await authFetch(`/api/gmail/reviews?${params}`);
      if (!response.ok) {
        push("error", "Could not load Gmail review queue.");
        return;
      }
      const data = await response.json();
      setItems(data.items || []);
      setPage(data.page || nextPage);
      setTotal(data.total || 0);
      setPageCount(data.page_count || 1);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(1);
  }, [statusFilter]);

  async function approveReview(id: number) {
    setActionLoading(id);
    try {
      const response = await authFetch(`/api/gmail/reviews/${id}/approve`, { method: "POST" });
      if (!response.ok) {
        push("error", "Could not approve review item.");
        return;
      }
      push("success", "Review approved and job ingested.");
      await load(page);
    } finally {
      setActionLoading(null);
    }
  }

  async function correctReview(id: number, title: string, company: string) {
    setActionLoading(id);
    try {
      const response = await authFetch(`/api/gmail/reviews/${id}/correct`, {
        method: "POST",
        body: JSON.stringify({ title, company }),
      });
      if (!response.ok) {
        push("error", "Could not correct and approve review item.");
        return;
      }
      push("success", "Corrections saved and job ingested.");
      await load(page);
    } finally {
      setActionLoading(null);
    }
  }

  async function rejectReview(id: number) {
    setActionLoading(id);
    try {
      const response = await authFetch(`/api/gmail/reviews/${id}/reject`, { method: "POST" });
      if (!response.ok) {
        push("error", "Could not reject review item.");
        return;
      }
      push("success", "Review item rejected.");
      await load(page);
    } finally {
      setActionLoading(null);
    }
  }

  return (
    <div>
      <ToastStack toasts={toasts} onDismiss={dismiss} />
      <h1>Gmail Ingestion Review</h1>
      <p>
        Low-confidence or unrecognized Gmail alerts are quarantined here. Approve, correct, or reject.
      </p>

      <div className="card">
        <label>
          Status filter{" "}
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All</option>
            <option value="quarantined">Quarantined</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </select>
        </label>

        {loading ? (
          <p className="loading-inline">Loading review queue…</p>
        ) : items.length === 0 ? (
          <p>No quarantined Gmail messages.</p>
        ) : (
          <>
            <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Label</th>
                  <th>Sender</th>
                  <th>Subject</th>
                  <th>Confidence</th>
                  <th>Ignored reason</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.created_at ? new Date(item.created_at).toLocaleString() : "—"}</td>
                    <td>{item.gmail_label || "—"}</td>
                    <td>{item.sender || "—"}</td>
                    <td>{item.subject || "—"}</td>
                    <td>{item.confidence != null ? `${Math.round(item.confidence * 100)}%` : "—"}</td>
                    <td>{item.ignored_reason || "—"}</td>
                    <td>{item.status}</td>
                    <td>
                      {(item.status === "quarantined" || item.status === "pending") && (
                        <div className="actions">
                          <button
                            type="button"
                            disabled={actionLoading === item.id}
                            onClick={() => approveReview(item.id)}
                          >
                            Approve
                          </button>
                          <button
                            type="button"
                            disabled={actionLoading === item.id}
                            onClick={() => {
                              const title = window.prompt("Correct job title", item.subject || "");
                              const company = window.prompt("Correct company name", "");
                              if (title && company) correctReview(item.id, title, company);
                            }}
                          >
                            Correct
                          </button>
                          <button
                            type="button"
                            disabled={actionLoading === item.id}
                            onClick={() => rejectReview(item.id)}
                          >
                            {actionLoading === item.id ? "Working…" : "Reject"}
                          </button>
                        </div>
                      )}
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
    </div>
  );
}
