"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

type LedgerRow = {
  id: number;
  company_id: number;
  job_id: number | null;
  status: string;
  normalized_title: string | null;
  submitted_at: string | null;
};

type Company = {
  id: number;
  canonical_name: string;
  normalized_name: string;
};

export default function CompaniesPage() {
  const [ledger, setLedger] = useState<LedgerRow[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);

  function token() {
    return localStorage.getItem("careeros_token") || "";
  }

  useEffect(() => {
    const headers = { Authorization: `Bearer ${token()}` };
    fetch(`${API_BASE}/api/companies/ledger`, { headers })
      .then((res) => res.json())
      .then(setLedger);
    fetch(`${API_BASE}/api/companies`, { headers })
      .then((res) => res.json())
      .then(setCompanies);
  }, []);

  const companyName = (id: number) =>
    companies.find((c) => c.id === id)?.canonical_name ?? `Company #${id}`;

  return (
    <div>
      <h1>Company Ledger</h1>
      <p>Application history and duplicate-protection audit trail.</p>
      <div className="card">
        <h3>Registered companies ({companies.length})</h3>
        <ul>
          {companies.map((c) => (
            <li key={c.id}>
              {c.canonical_name} <small>({c.normalized_name})</small>
            </li>
          ))}
        </ul>
      </div>
      <div className="card">
        <h3>Application ledger</h3>
        {ledger.length === 0 ? (
          <p>No ledger entries yet.</p>
        ) : (
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
                  <td>{companyName(row.company_id)}</td>
                  <td>{row.normalized_title ?? "—"}</td>
                  <td>{row.status}</td>
                  <td>{row.submitted_at ? new Date(row.submitted_at).toLocaleDateString() : "—"}</td>
                  <td>
                    {row.job_id ? (
                      <a href={`/jobs/${row.job_id}`}>#{row.job_id}</a>
                    ) : (
                      "—"
                    )}
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
