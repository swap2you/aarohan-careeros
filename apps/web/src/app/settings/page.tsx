"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

export default function SettingsPage() {
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [validation, setValidation] = useState<Record<string, unknown> | null>(null);
  const [message, setMessage] = useState("");

  function token() {
    return localStorage.getItem("careeros_token") || "";
  }

  useEffect(() => {
    fetch(`${API_BASE}/api/integrations/status`, { headers: { Authorization: `Bearer ${token()}` } })
      .then((res) => res.json())
      .then(setStatus);
    fetch(`${API_BASE}/api/validation/latest`, { headers: { Authorization: `Bearer ${token()}` } })
      .then((res) => res.json())
      .then(setValidation);
  }, []);

  async function connect(service: string) {
    const response = await fetch(`${API_BASE}/api/integrations/google/connect?service=${service}`, {
      headers: { Authorization: `Bearer ${token()}` },
    });
    const data = await response.json();
    if (data.auth_url) window.open(data.auth_url, "_blank");
    else setMessage(data.message || "OAuth not configured — use fixture mode for local testing.");
  }

  async function disconnect(service: string) {
    await fetch(`${API_BASE}/api/integrations/google/disconnect?service=${service}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token()}` },
    });
    setMessage(`Disconnected ${service}`);
  }

  async function syncGmail() {
    const response = await fetch(`${API_BASE}/api/integrations/gmail/sync`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token()}` },
    });
    setMessage(JSON.stringify(await response.json()));
  }

  async function syncFixtureGmail() {
    const response = await fetch(`${API_BASE}/api/integrations/gmail/sync-fixture`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token()}` },
    });
    setMessage(JSON.stringify(await response.json()));
  }

  async function runValidation() {
    setMessage("Running local validation...");
    const response = await fetch(`${API_BASE}/api/validation/run`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token()}` },
    });
    const data = await response.json();
    setValidation(data);
    setMessage(`Validation ${data.status}`);
  }

  return (
    <div>
      <h1>Settings & Integrations</h1>
      <div className="card">
        <h3>Integration Status</h3>
        <pre>{JSON.stringify(status, null, 2)}</pre>
        <div className="actions">
          <button onClick={() => connect("google")}>Connect Google</button>
          <button onClick={() => disconnect("all")}>Disconnect Google</button>
          <button onClick={syncGmail}>Sync Gmail (read-only)</button>
          <button onClick={syncFixtureGmail}>Sync Gmail Fixture</button>
        </div>
      </div>
      <div className="card">
        <h3>Local Validation</h3>
        <button onClick={runValidation}>Run Local Validation</button>
        <pre>{JSON.stringify(validation, null, 2)}</pre>
      </div>
      {message && <p className="status">{message}</p>}
      <div className="card">
        <p>Secrets are loaded from PowerShell SecretStore via Start-Aarohan.ps1. No credentials in Git.</p>
        <p>Human approval required before external submission or messaging.</p>
      </div>
    </div>
  );
}
