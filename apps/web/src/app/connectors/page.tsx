"use client";

import { useCallback, useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

type Connector = {
  provider_id: string;
  label: string;
  state: string;
  source_name: string;
  requires_api_key: boolean;
  attribution?: string | null;
  message?: string | null;
  last_run_at?: string | null;
  last_job_count?: number | null;
};

export default function ConnectorsPage() {
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [message, setMessage] = useState("");
  const [params, setParams] = useState<Record<string, string>>({
    board_token: "",
    company_slug: "",
    job_board_name: "",
  });

  function token() {
    return localStorage.getItem("careeros_token") || "";
  }

  const load = useCallback(() => {
    fetch(`${API_BASE}/api/connectors`, { headers: { Authorization: `Bearer ${token()}` } })
      .then((res) => res.json())
      .then((data) => setConnectors(data.connectors || []));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function run(providerId: string, useFixture: boolean) {
    setMessage(`Running ${providerId}...`);
    const runParams: Record<string, string> = {};
    if (providerId === "greenhouse" && params.board_token) runParams.board_token = params.board_token;
    if (providerId === "lever" && params.company_slug) runParams.company_slug = params.company_slug;
    if (providerId === "ashby" && params.job_board_name) runParams.job_board_name = params.job_board_name;

    const response = await fetch(`${API_BASE}/api/connectors/${providerId}/run`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token()}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ use_fixture: useFixture, params: runParams }),
    });
    const data = await response.json();
    if (!response.ok) {
      setMessage(data.detail || "Run failed");
      return;
    }
    setMessage(`${providerId}: ingested ${data.ingested} jobs (${data.state})`);
    load();
  }

  function stateClass(state: string) {
    if (state === "READY") return "risk-green";
    if (state === "NOT_CONFIGURED") return "risk-amber";
    return "risk-red";
  }

  return (
    <div>
      <h1>Job Connectors</h1>
      <p>Source health, configuration status, and ad hoc ingestion runs.</p>
      <div className="card">
        <h3>Connector parameters</h3>
        <label>Greenhouse board token</label>
        <input
          value={params.board_token}
          onChange={(e) => setParams({ ...params, board_token: e.target.value })}
        />
        <label>Lever company slug</label>
        <input
          value={params.company_slug}
          onChange={(e) => setParams({ ...params, company_slug: e.target.value })}
        />
        <label>Ashby job board name</label>
        <input
          value={params.job_board_name}
          onChange={(e) => setParams({ ...params, job_board_name: e.target.value })}
        />
      </div>
      {connectors.map((c) => (
        <div key={c.provider_id} className={`card ${stateClass(c.state)}`}>
          <h3>
            {c.label} <small>({c.state})</small>
          </h3>
          <p>Source: {c.source_name}</p>
          {c.message && <p>{c.message}</p>}
          {c.attribution && <p>{c.attribution}</p>}
          {c.last_run_at && (
            <p>
              Last run: {new Date(c.last_run_at).toLocaleString()} — {c.last_job_count ?? 0} jobs
            </p>
          )}
          <div className="actions">
            <button
              type="button"
              disabled={c.state === "DISABLED"}
              onClick={() => run(c.provider_id, false)}
            >
              Run live
            </button>
            <button type="button" onClick={() => run(c.provider_id, true)}>
              Run fixture
            </button>
          </div>
        </div>
      ))}
      {message && <p className="status">{message}</p>}
    </div>
  );
}
