"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";

export default function AnalyticsPage() {
  const { apiFetch, status: authStatus } = useAuth();
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [budget, setBudget] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    if (authStatus !== "authenticated") return;
    apiFetch("/api/analytics")
      .then((res) => (res.ok ? res.json() : null))
      .then(setData);
    apiFetch("/api/ai/budget")
      .then((res) => (res.ok ? res.json() : null))
      .then(setBudget);
  }, [apiFetch, authStatus]);

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
