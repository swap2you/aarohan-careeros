"use client";

import { useEffect, useState } from "react";
import { authFetch } from "@/lib/api";

export default function ConsultingPage() {
  const [leads, setLeads] = useState<Array<{ id: number; company: string; recommended_service?: string }>>([]);
  const [company, setCompany] = useState("");
  const [problem, setProblem] = useState("");

  async function load() {
    const response = await authFetch(`/api/consulting/leads`);
    setLeads(await response.json());
  }

  useEffect(() => {
    load();
  }, []);

  async function createLead() {
    await authFetch(`/api/consulting/leads`, {
      method: "POST",
      body: JSON.stringify({ company, problem_summary: problem }),
    });
    setCompany("");
    setProblem("");
    load();
  }

  return (
    <div>
      <h1>Consulting Leads (Preview)</h1>
      <p className="status">Minimal preview workflow — not final UAT scope.</p>
      <div className="card">
        <input placeholder="Company" value={company} onChange={(e) => setCompany(e.target.value)} />
        <textarea
          placeholder="Problem summary"
          value={problem}
          onChange={(e) => setProblem(e.target.value)}
          rows={4}
          style={{ width: "100%" }}
        />
        <button onClick={createLead}>Create Lead</button>
      </div>
      <div className="card">
        {leads.map((lead) => (
          <div key={lead.id}>
            {lead.company} — {lead.recommended_service}
          </div>
        ))}
      </div>
    </div>
  );
}
