"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";

type Application = {
  id: number;
  job_id: number;
  state: string;
  cover_letter?: string;
  fit_analysis?: string;
  packet_metadata?: { preview_text?: string; missing_evidence_warnings?: string[] };
};

export default function ApprovalsPage() {
  const { apiFetch, status: authStatus } = useAuth();
  const [items, setItems] = useState<Application[]>([]);
  const [preview, setPreview] = useState<Application | null>(null);

  const load = useCallback(async () => {
    const response = await apiFetch("/api/applications/queue");
    if (response.ok) setItems(await response.json());
  }, [apiFetch]);

  useEffect(() => {
    if (authStatus === "authenticated") void load();
  }, [authStatus, load]);

  async function act(id: number, action: string) {
    await apiFetch(`/api/applications/${id}/actions`, {
      method: "POST",
      body: JSON.stringify({ action }),
    });
    load();
  }

  async function showPreview(id: number) {
    const response = await apiFetch(`/api/validation/applications/${id}/preview`);
    if (response.ok) setPreview(await response.json());
  }

  async function download(id: number, fileType: "docx" | "pdf") {
    const response = await apiFetch(`/api/validation/applications/${id}/download/${fileType}`);
    if (!response.ok) return;
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `application_${id}.${fileType}`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div>
      <h1>Approval Queue</h1>
      <div className="card">
        {items.length === 0 ? (
          <p>No items in queue.</p>
        ) : (
          items.map((item) => (
            <div key={item.id} className="queue-item">
              <strong>Application #{item.id}</strong> — Job {item.job_id} — {item.state}
              <div className="actions">
                <button onClick={() => showPreview(item.id)}>Preview</button>
                <button onClick={() => download(item.id, "docx")}>DOCX</button>
                <button onClick={() => download(item.id, "pdf")}>PDF</button>
                <button onClick={() => act(item.id, "approve")}>Approve</button>
                <button onClick={() => act(item.id, "needs_edit")}>Needs Edit</button>
                <button onClick={() => act(item.id, "hold")}>Hold</button>
                <button onClick={() => act(item.id, "reject")}>Reject</button>
                <button onClick={() => act(item.id, "mark_submitted")}>Mark Submitted</button>
              </div>
            </div>
          ))
        )}
      </div>
      {preview && (
        <div className="card">
          <h3>Packet Preview</h3>
          <pre>{preview.fit_analysis}</pre>
          <pre>{preview.cover_letter}</pre>
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
        </div>
      )}
    </div>
  );
}
