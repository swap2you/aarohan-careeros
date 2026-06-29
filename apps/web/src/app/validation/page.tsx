"use client";

import { useEffect, useState } from "react";
import { API_BASE, authFetch } from "@/lib/api";

export default function ValidationCenterPage() {
  const [validation, setValidation] = useState<Record<string, unknown> | null>(null);
  const [message, setMessage] = useState("");


  useEffect(() => {
    authFetch(`/api/validation/latest`)
      .then((res) => res.json())
      .then(setValidation);
  }, []);

  async function runValidation() {
    setMessage("Running local validation...");
    const response = await authFetch(`/api/validation/run`, {
      method: "POST", });
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
