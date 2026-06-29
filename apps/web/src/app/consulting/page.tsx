"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";

export default function ConsultingPage() {
  const { apiFetch, status: authStatus } = useAuth();
  const [leads, setLeads] = useState<Array<{ id: number; company: string; recommended_service?: string }>>([]);
  const [company, setCompany] = useState("");
  const [problem, setProblem] = useState("");

  const load = useCallback(async () => {
    const response = await apiFetch("/api/consulting/leads");
    if (response.ok) setLeads(await response.json());
  }, [apiFetch]);

  useEffect(() => {
    if (authStatus === "authenticated") void load();
  }, [authStatus, load]);

  async function createLead() {
    await apiFetch("/api/consulting/leads", {
      method: "POST",
      body: JSON.stringify({ company, problem_summary: problem }),
    });
    setCompany("");
    setProblem("");
    load();
  }

  return (
    <div>
      <h1>Consulting Leads</h1>
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
