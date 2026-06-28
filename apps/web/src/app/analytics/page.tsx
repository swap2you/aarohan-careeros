"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

export default function AnalyticsPage() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [budget, setBudget] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("careeros_token");
    if (!token) return;
    fetch(`${API_BASE}/api/analytics`, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => res.json())
      .then(setData);
    fetch(`${API_BASE}/api/ai/budget`, { headers: { Authorization: `Bearer ${token}` } })
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
