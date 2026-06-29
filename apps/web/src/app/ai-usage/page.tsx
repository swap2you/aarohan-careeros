"use client";

import { useEffect, useState } from "react";
import { authFetch } from "@/lib/api";

type Usage = {
  id: number;
  operation: string;
  cost_usd: number;
  model: string | null;
  created_at: string;
};

export default function AiUsagePage() {
  const [usage, setUsage] = useState<Usage[]>([]);
  const [budget, setBudget] = useState<Record<string, unknown> | null>(null);


  useEffect(() => {
    authFetch(`/api/ai/usage`).then((r) => r.json()).then(setUsage);
    authFetch(`/api/ai/budget`).then((r) => r.json()).then(setBudget);
  }, []);

  return (
    <div>
      <h1>AI Usage and Cost</h1>
      <div className="card">
        <h3>Budget Status</h3>
        <pre>{JSON.stringify(budget, null, 2)}</pre>
      </div>
      <div className="card">
        <h3>Recent Usage</h3>
        <table>
          <thead>
            <tr>
              <th>Operation</th>
              <th>Cost (USD)</th>
              <th>Model</th>
              <th>When</th>
            </tr>
          </thead>
          <tbody>
            {usage.map((row) => (
              <tr key={row.id}>
                <td>{row.operation}</td>
                <td>{row.cost_usd.toFixed(2)}</td>
                <td>{row.model ?? "—"}</td>
                <td>{new Date(row.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
