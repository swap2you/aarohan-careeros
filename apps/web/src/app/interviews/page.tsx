"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";

export default function InterviewsPage() {
  const { apiFetch, status: authStatus } = useAuth();
  const [jobId, setJobId] = useState("1");
  const [pack, setPack] = useState<Record<string, unknown> | null>(null);

  async function generate() {
    const response = await apiFetch(`/api/interviews/jobs/${jobId}/generate`, { method: "POST" });
    if (response.ok) setPack(await response.json());
  }

  useEffect(() => {
    if (authStatus !== "authenticated") return;
    apiFetch(`/api/interviews/${jobId}`)
      .then((res) => (res.ok ? res.json() : null))
      .then(setPack);
  }, [apiFetch, authStatus, jobId]);

  return (
    <div>
      <h1>Interview Preparation</h1>
      <input value={jobId} onChange={(e) => setJobId(e.target.value)} />
      <button onClick={generate}>Generate Interview Pack</button>
      {pack && (
        <div className="card">
          <pre>{JSON.stringify(pack, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
