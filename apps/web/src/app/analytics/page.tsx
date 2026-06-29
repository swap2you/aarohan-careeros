"use client";

import { useEffect, useState } from "react";
import { authFetch } from "@/lib/api";

export default function AnalyticsPage() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [budget, setBudget] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    authFetch(`/api/analytics`)
      .then((res) => res.json())
      .then(setData);
    authFetch(`/api/ai/budget`)
      .then((res) => res.json())
      .then(setBudget);
  }, []);

  return (
    <div>
      <h1>Analytics & AI Spend</h1>
      <div className="card">
        <h3>Pipeline</h3>
        <pre>{JSON.stringify(data, null, 2)}</pre>
      </div>
      <div className="card">
        <h3>AI Budget</h3>
        <pre>{JSON.stringify(budget, null, 2)}</pre>
      </div>
    </div>
  );
}
