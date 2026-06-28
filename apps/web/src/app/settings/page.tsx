"use client";

import { useCallback, useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

type DriveRoot = {
  configured_folder_id?: string | null;
  active_folder_id?: string | null;
  source?: string | null;
  accessible?: boolean;
  warning?: string | null;
  subfolders?: Record<string, string> | null;
  app_root_folder_name?: string;
};

type IntegrationStatus = {
  connected_account?: string;
  google_connected?: boolean;
  dedicated_gmail?: string;
  drive_root?: DriveRoot;
  drive_root_folder_id?: string;
  google?: { connected?: boolean; account_email?: string };
  gmail?: { connected?: boolean };
  drive?: { connected?: boolean };
  fixture_mode?: boolean;
};

export default function SettingsPage() {
  const [status, setStatus] = useState<IntegrationStatus | null>(null);
  const [validation, setValidation] = useState<Record<string, unknown> | null>(null);
  const [message, setMessage] = useState("");

  function token() {
    return localStorage.getItem("careeros_token") || "";
  }

  const loadStatus = useCallback(() => {
    fetch(`${API_BASE}/api/integrations/status`, { headers: { Authorization: `Bearer ${token()}` } })
      .then((res) => res.json())
      .then(setStatus)
      .catch(() => setMessage("Failed to load integration status"));
  }, []);

  useEffect(() => {
    loadStatus();
    fetch(`${API_BASE}/api/validation/latest`, { headers: { Authorization: `Bearer ${token()}` } })
      .then((res) => res.json())
      .then(setValidation);
  }, [loadStatus]);

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
    loadStatus();
  }

  async function createDriveRoot() {
    setMessage("Creating Aarohan Drive root...");
    const response = await fetch(`${API_BASE}/api/integrations/google/drive/create-root`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token()}` },
    });
    const data = await response.json();
    if (!response.ok) {
      setMessage(data.detail || "Drive root creation failed");
      return;
    }
    setMessage(`Drive root created: ${data.root_folder_id}`);
    loadStatus();
  }

  async function syncDriveFolders() {
    const response = await fetch(`${API_BASE}/api/integrations/google/drive/folders`, {
      headers: { Authorization: `Bearer ${token()}` },
    });
    const data = await response.json();
    if (!response.ok) {
      setMessage(data.detail || "Drive folder sync failed");
      return;
    }
    setMessage(`Drive folders synced (${Object.keys(data.folders || {}).length} entries)`);
    loadStatus();
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

  const driveRoot = status?.drive_root;
  const showCreateRoot = Boolean(
    status?.google_connected && driveRoot && !driveRoot.accessible,
  );

  return (
    <div>
      <h1>Settings & Integrations</h1>
      <div className="card">
        <h3>Google Integration</h3>
        <p><strong>Connected account:</strong> {status?.connected_account || "—"}</p>
        <p><strong>Dedicated Gmail:</strong> {status?.dedicated_gmail || "—"}</p>
        <p><strong>Google connected:</strong> {status?.google_connected ? "yes" : "no"}</p>
        <div className="actions">
          <button onClick={() => connect("google")}>Connect Google</button>
          <button onClick={() => disconnect("all")}>Disconnect Google</button>
          <button onClick={syncGmail}>Sync Gmail (read-only)</button>
          <button onClick={syncFixtureGmail}>Sync Gmail Fixture</button>
        </div>
      </div>
      <div className="card">
        <h3>Google Drive Root</h3>
        <p><strong>Configured root ID:</strong> {driveRoot?.configured_folder_id || "—"}</p>
        <p><strong>Active root ID:</strong> {driveRoot?.active_folder_id || "—"}</p>
        <p><strong>Root source:</strong> {driveRoot?.source || "—"}</p>
        <p><strong>Accessible (drive.file):</strong> {driveRoot?.accessible ? "yes" : "no"}</p>
        {driveRoot?.warning && <p className="error">{driveRoot.warning}</p>}
        {showCreateRoot && (
          <button onClick={createDriveRoot}>Create Aarohan Drive Root</button>
        )}
        <button onClick={syncDriveFolders}>Sync Drive Subfolders</button>
        {driveRoot?.subfolders && (
          <>
            <h4>Subfolder IDs</h4>
            <pre>{JSON.stringify(driveRoot.subfolders, null, 2)}</pre>
          </>
        )}
      </div>
      <div className="card">
        <h3>Raw Integration Status</h3>
        <pre>{JSON.stringify(status, null, 2)}</pre>
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
