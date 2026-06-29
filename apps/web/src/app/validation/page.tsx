"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";

export default function ValidationCenterPage() {
  const { apiFetch, status: authStatus } = useAuth();
  const [validation, setValidation] = useState<Record<string, unknown> | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (authStatus !== "authenticated") return;
    apiFetch("/api/validation/latest")
      .then((res) => (res.ok ? res.json() : null))
      .then(setValidation);
  }, [apiFetch, authStatus]);

  async function runValidation() {
    setMessage("Running local validation...");
    const response = await apiFetch("/api/validation/run", { method: "POST" });
    const data = await response.json();
    setValidation(data);
    setMessage(`Validation ${data.status}`);
  }

  return (
    <div>
      <h1>Validation Center</h1>
      <div className="card">
        <button onClick={runValidation}>Run Local Validation</button>
        {message && <p className="status">{message}</p>}
        <pre>{JSON.stringify(validation, null, 2)}</pre>
      </div>
    </div>
  );
}
