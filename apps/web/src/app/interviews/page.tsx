"use client";

import { useEffect, useState } from "react";
import { authFetch } from "@/lib/api";

export default function InterviewsPage() {
  const [jobId, setJobId] = useState("1");
  const [pack, setPack] = useState<Record<string, unknown> | null>(null);

  async function generate() {
    const response = await authFetch(`/api/interviews/jobs/${jobId}/generate`, {
      method: "POST",
    });
    setPack(await response.json());
  }

  useEffect(() => {
    authFetch(`/api/interviews/${jobId}`)
      .then((res) => (res.ok ? res.json() : null))
      .then(setPack);
  }, [jobId]);

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
