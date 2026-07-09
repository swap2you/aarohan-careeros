"use client";

import { useEffect, useState } from "react";

import { authFetch } from "@/lib/api";

type UsageItem = {
  id: number;
  operation: string;
  cost_usd: number;
  cost_label: string;
  model: string;
  token_count: number;
  tokens_in: number;
  tokens_out: number;
  created_at: string;
};

type Budget = {
  monthly_spend_usd: number;
  soft_cap_usd: number;
  hard_cap_usd: number;
  remaining_usd: number;
  percent_of_hard_cap: number;
  note: string;
};

export default function AiUsagePage() {
  const [usage, setUsage] = useState<UsageItem[]>([]);
  const [budget, setBudget] = useState<Budget | null>(null);
  const [page, setPage] = useState(1);
  const [pageCount, setPageCount] = useState(1);
  const [total, setTotal] = useState(0);

  async function load(p = page) {
    const res = await authFetch(`/api/ai/usage?page=${p}&page_size=25`);
    const data = await res.json();
    setUsage(data.items || []);
    setBudget(data.budget || null);
    setPage(data.page || p);
    setPageCount(data.page_count || 1);
    setTotal(data.total || 0);
  }

  useEffect(() => {
    load(1);
  }, []);

  return (
    <div>
      <h1>AI Usage and Cost</h1>
      {budget && (
        <div className="card">
          <h3>Monthly budget</h3>
          <p>
            Recorded spend: <strong>${budget.monthly_spend_usd.toFixed(4)}</strong> (estimated) · Remaining:{" "}
            <strong>${budget.remaining_usd.toFixed(4)}</strong> · Hard cap: ${budget.hard_cap_usd.toFixed(2)}
          </p>
          <p className="muted">{budget.note}</p>
          <p className="muted">{budget.percent_of_hard_cap}% of hard cap used</p>
        </div>
      )}
      <div className="card table-card">
        <h3>Recent usage ({total})</h3>
        <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Operation</th>
              <th>Model</th>
              <th>Tokens</th>
              <th>Cost</th>
              <th>When</th>
            </tr>
          </thead>
          <tbody>
            {usage.map((row) => (
              <tr key={row.id}>
                <td>{row.operation}</td>
                <td>{row.model}</td>
                <td>{row.token_count}</td>
                <td>
                  ${row.cost_usd.toFixed(4)} ({row.cost_label})
                </td>
                <td>{new Date(row.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
        <div className="pagination">
          <span>
            page {page} of {pageCount}
          </span>
          <button type="button" disabled={page <= 1} onClick={() => load(page - 1)}>
            Previous
          </button>
          <button type="button" disabled={page >= pageCount} onClick={() => load(page + 1)}>
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
