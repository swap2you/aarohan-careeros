"use client";

import { useEffect, useState } from "react";

import { authFetch } from "@/lib/api";

type AuditRow = {
  id: number;
  event_type: string;
  event_label: string;
  actor: string | null;
  resource_type: string | null;
  resource_id: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
};

export default function AuditPage() {
  const [items, setItems] = useState<AuditRow[]>([]);
  const [page, setPage] = useState(1);
  const [pageCount, setPageCount] = useState(1);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<AuditRow | null>(null);
  const [loading, setLoading] = useState(false);

  async function load(nextPage = page, q = search) {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(nextPage), page_size: "25" });
      if (q) params.set("search", q);
      const res = await authFetch(`/api/audit?${params}`);
      const data = await res.json();
      setItems(data.items || []);
      setPage(data.page || nextPage);
      setPageCount(data.page_count || 1);
      setTotal(data.total || 0);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(1);
  }, []);

  return (
    <div>
      <h1>Audit Log</h1>
      <p>Supervised actions across jobs, packets, connectors, and integrations.</p>
      <div className="card">
        <label>
          Search{" "}
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load(1, search)}
          />
        </label>
        <button type="button" onClick={() => load(1, search)}>
          Filter
        </button>
        {loading ? (
          <p className="loading-inline">Loading…</p>
        ) : (
          <>
            <table>
              <thead>
                <tr>
                  <th>Event</th>
                  <th>Actor</th>
                  <th>When (local)</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {items.map((log) => (
                  <tr key={log.id}>
                    <td>{log.event_label}</td>
                    <td>{log.actor || "—"}</td>
                    <td>{new Date(log.created_at).toLocaleString()}</td>
                    <td>
                      <button type="button" onClick={() => setSelected(log)}>
                        Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="pagination">
              <span>
                {total} events · page {page} of {pageCount}
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
      {selected && (
        <div className="card">
          <h3>{selected.event_label}</h3>
          <p>
            {selected.actor} · {new Date(selected.created_at).toLocaleString()}
          </p>
          {selected.resource_type && (
            <p>
              Resource: {selected.resource_type} {selected.resource_id}
            </p>
          )}
          {selected.details && (
            <ul>
              {Object.entries(selected.details).map(([k, v]) => (
                <li key={k}>
                  <strong>{k}:</strong> {typeof v === "object" ? JSON.stringify(v) : String(v)}
                </li>
              ))}
            </ul>
          )}
          <button type="button" onClick={() => setSelected(null)}>
            Close
          </button>
        </div>
      )}
    </div>
  );
}
