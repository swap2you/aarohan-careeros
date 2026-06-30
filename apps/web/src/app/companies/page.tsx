"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { authFetch } from "@/lib/api";

type LedgerRow = {
  id: number;
  company_id: number;
  company_name: string | null;
  job_id: number | null;
  status: string;
  normalized_title: string | null;
  submitted_at: string | null;
};

type Company = {
  id: number;
  canonical_name: string;
  normalized_name: string;
  application_count: number;
};

export default function CompaniesPage() {
  const [ledger, setLedger] = useState<LedgerRow[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [ledgerPage, setLedgerPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [ledgerTotal, setLedgerTotal] = useState(0);
  const [pageCount, setPageCount] = useState(1);
  const [ledgerPageCount, setLedgerPageCount] = useState(1);

  async function loadCompanies(p = page, q = search) {
    const params = new URLSearchParams({ page: String(p), page_size: "25" });
    if (q) params.set("search", q);
    const res = await authFetch(`/api/companies?${params}`);
    const data = await res.json();
    setCompanies(data.items || []);
    setPage(data.page || p);
    setTotal(data.total || 0);
    setPageCount(data.page_count || 1);
  }

  async function loadLedger(p = ledgerPage, q = search) {
    const params = new URLSearchParams({ page: String(p), page_size: "25" });
    if (q) params.set("search", q);
    const res = await authFetch(`/api/companies/ledger?${params}`);
    const data = await res.json();
    setLedger(data.items || []);
    setLedgerPage(data.page || p);
    setLedgerTotal(data.total || 0);
    setLedgerPageCount(data.page_count || 1);
  }

  useEffect(() => {
    loadCompanies(1);
    loadLedger(1);
  }, []);

  return (
    <div>
      <h1>Company Ledger</h1>
      <p>Valid company records and application history (fixture/test data excluded).</p>
      <div className="card">
        <label>
          Search{" "}
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                loadCompanies(1, search);
                loadLedger(1, search);
              }
            }}
          />
        </label>
        <button
          type="button"
          onClick={() => {
            loadCompanies(1, search);
            loadLedger(1, search);
          }}
        >
          Search
        </button>
      </div>
      <div className="card">
        <h3>Registered companies ({total})</h3>
        <table>
          <thead>
            <tr>
              <th>Company</th>
              <th>Applications</th>
            </tr>
          </thead>
          <tbody>
            {companies.map((c) => (
              <tr key={c.id}>
                <td>{c.canonical_name}</td>
                <td>{c.application_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="pagination">
          <span>
            page {page} of {pageCount}
          </span>
          <button type="button" disabled={page <= 1} onClick={() => loadCompanies(page - 1)}>
            Previous
          </button>
          <button type="button" disabled={page >= pageCount} onClick={() => loadCompanies(page + 1)}>
            Next
          </button>
        </div>
      </div>
      <div className="card">
        <h3>Application ledger ({ledgerTotal})</h3>
        {ledger.length === 0 ? (
          <p>No ledger entries yet.</p>
        ) : (
          <>
            <table>
              <thead>
                <tr>
                  <th>Company</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Submitted</th>
                  <th>Job</th>
                </tr>
              </thead>
              <tbody>
                {ledger.map((row) => (
                  <tr key={row.id}>
                    <td>{row.company_name ?? "—"}</td>
                    <td>{row.normalized_title ?? "—"}</td>
                    <td>{row.status}</td>
                    <td>{row.submitted_at ? new Date(row.submitted_at).toLocaleDateString() : "—"}</td>
                    <td>{row.job_id ? <Link href={`/jobs/${row.job_id}`}>View job</Link> : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="pagination">
              <span>
                page {ledgerPage} of {ledgerPageCount}
              </span>
              <button type="button" disabled={ledgerPage <= 1} onClick={() => loadLedger(ledgerPage - 1)}>
                Previous
              </button>
              <button
                type="button"
                disabled={ledgerPage >= ledgerPageCount}
                onClick={() => loadLedger(ledgerPage + 1)}
              >
                Next
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
