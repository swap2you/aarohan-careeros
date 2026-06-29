"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";

type DriveRoot = {
  configured_folder_id?: string | null;
  active_folder_id?: string | null;
  source?: string | null;
  accessible?: boolean;
  warning?: string | null;
  subfolders?: Record<string, string> | null;
  app_root_folder_name?: string;
};

type GoogleStatus = {
  connected?: boolean;
  account_email?: string;
  connection_status?: string;
  last_refresh_at?: string | null;
};

type IntegrationStatus = {
  connected_account?: string;
  google_connected?: boolean;
  dedicated_gmail?: string;
  drive_root?: DriveRoot;
  google?: GoogleStatus;
  gmail?: { connected?: boolean };
  drive?: { connected?: boolean };
  fixture_mode?: boolean;
  oauth_configured?: boolean;
};

type ApplicationMode = {
  id: string;
  label: string;
  description: string;
  enabled: boolean;
};

function googleStatusLabel(status?: IntegrationStatus) {
  const conn = status?.google?.connection_status;
  if (conn === "reconnect_required") return "Reconnect required";
  if (status?.google_connected) return "Connected";
  return "Disconnected";
}

function capabilitySummary(status: IntegrationStatus | null) {
  if (!status?.google_connected) return "Gmail and Drive not connected.";
  const parts = [];
  if (status.gmail?.connected ?? status.google?.connected) parts.push("Gmail read-only");
  if (status.drive?.connected ?? status.google?.connected) parts.push("Drive file scope");
  return parts.join(" · ") || "Google scopes granted";
}

export default function SettingsPage() {
  const { apiFetch, status: authStatus } = useAuth();
  const [status, setStatus] = useState<IntegrationStatus | null>(null);
  const [validation, setValidation] = useState<Record<string, unknown> | null>(null);
  const [applicationModes, setApplicationModes] = useState<ApplicationMode[]>([]);
  const [message, setMessage] = useState("");

  const loadStatus = useCallback(() => {
    apiFetch("/api/integrations/status")
      .then((res) => (res.ok ? res.json() : null))
      .then(setStatus)
      .catch(() => setMessage("Failed to load integration status"));
  }, [apiFetch]);

  useEffect(() => {
    if (authStatus !== "authenticated") return;
    loadStatus();
    apiFetch("/api/validation/latest")
      .then((res) => (res.ok ? res.json() : null))
      .then(setValidation);
    apiFetch("/api/companies/application-modes")
      .then((res) => (res.ok ? res.json() : { modes: [] }))
      .then((data) => setApplicationModes(data.modes || []));
  }, [apiFetch, authStatus, loadStatus]);

  async function connect(reconnect = false) {
    const response = await apiFetch(
      `/api/integrations/google/connect?service=google${reconnect ? "&reconnect=true" : ""}`,
    );
    const data = await response.json();
    if (data.auth_url) window.open(data.auth_url, "_blank");
    else setMessage(data.message || "OAuth not configured — use fixture mode for local testing.");
  }

  async function disconnect() {
    if (!window.confirm("Disconnect Google? You will need to reconnect to use Gmail and Drive.")) return;
    await apiFetch("/api/integrations/google/disconnect?service=all", { method: "POST" });
    setMessage("Google disconnected");
    loadStatus();
  }

  async function createDriveRoot() {
    setMessage("Creating Aarohan Drive root...");
    const response = await apiFetch("/api/integrations/google/drive/create-root", { method: "POST" });
    const data = await response.json();
    if (!response.ok) {
      setMessage(data.detail || "Drive root creation failed");
      return;
    }
    setMessage(`Drive root created: ${data.root_folder_id}`);
    loadStatus();
  }

  async function syncDriveFolders() {
    const response = await apiFetch("/api/integrations/google/drive/folders");
    const data = await response.json();
    if (!response.ok) {
      setMessage(data.detail || "Drive folder sync failed");
      return;
    }
    setMessage(`Drive folders synced (${Object.keys(data.folders || {}).length} entries)`);
    loadStatus();
  }

  async function syncGmail() {
    const response = await apiFetch("/api/integrations/gmail/sync", { method: "POST" });
    setMessage(JSON.stringify(await response.json()));
  }

  async function syncFixtureGmail() {
    const response = await apiFetch("/api/integrations/gmail/sync-fixture", { method: "POST" });
    setMessage(JSON.stringify(await response.json()));
  }

  async function runValidation() {
    setMessage("Running local validation...");
    const response = await apiFetch("/api/validation/run", { method: "POST" });
    const data = await response.json();
    setValidation(data);
    setMessage(`Validation ${data.status}`);
  }

  const driveRoot = status?.drive_root;
  const googleConn = status?.google?.connection_status;
  const showCreateRoot = Boolean(status?.google_connected && driveRoot && !driveRoot.accessible);
  const needsReconnect = googleConn === "reconnect_required";

  return (
    <div>
      <h1>Settings & Integrations</h1>
      <div className="card">
        <h3>Application Modes</h3>
        {applicationModes.map((mode) => (
          <div key={mode.id} className={mode.enabled ? "" : "mode-disabled"}>
            <p>
              <strong>{mode.label}</strong> {mode.enabled ? "(enabled)" : "(locked)"}
            </p>
            <p>{mode.description}</p>
          </div>
        ))}
      </div>
      <div className="card">
        <h3>Google Integration</h3>
        <p><strong>Status:</strong> {googleStatusLabel(status ?? undefined)}</p>
        <p><strong>Account:</strong> {status?.connected_account || status?.google?.account_email || "—"}</p>
        <p><strong>Capabilities:</strong> {capabilitySummary(status)}</p>
        <p><strong>Last token refresh:</strong>{" "}
          {status?.google?.last_refresh_at
            ? new Date(status.google.last_refresh_at).toLocaleString()
            : "—"}
        </p>
        <p><strong>Dedicated Gmail:</strong> {status?.dedicated_gmail || "—"}</p>
        {needsReconnect && (
          <p className="warn">Google refresh failed. Reconnect to restore Gmail and Drive access.</p>
        )}
        <div className="actions">
          {!status?.google_connected ? (
            <button type="button" onClick={() => connect(false)}>Connect Google</button>
          ) : needsReconnect ? (
            <button type="button" onClick={() => connect(true)}>Reconnect Google</button>
          ) : (
            <button type="button" onClick={() => connect(true)}>Reconnect Google</button>
          )}
          <button type="button" onClick={disconnect} disabled={!status?.google_connected}>
            Disconnect Google
          </button>
          <button type="button" onClick={syncGmail}>Sync Gmail (read-only)</button>
          {status?.fixture_mode && (
            <button type="button" onClick={syncFixtureGmail}>Sync Gmail Fixture</button>
          )}
        </div>
      </div>
      <div className="card">
        <h3>Google Drive Root</h3>
        <p><strong>Root status:</strong> {driveRoot?.accessible ? "Accessible" : driveRoot?.configured_folder_id ? "Configured" : "Not set"}</p>
        <p><strong>Configured root ID:</strong> {driveRoot?.configured_folder_id || "—"}</p>
        <p><strong>Active root ID:</strong> {driveRoot?.active_folder_id || "—"}</p>
        <p><strong>Root source:</strong> {driveRoot?.source || "—"}</p>
        {driveRoot?.warning && <p className="error">{driveRoot.warning}</p>}
        {showCreateRoot && (
          <button type="button" onClick={createDriveRoot}>Create Aarohan Drive Root</button>
        )}
        <button type="button" onClick={syncDriveFolders}>Sync Drive Subfolders</button>
        {driveRoot?.subfolders && (
          <>
            <h4>Subfolder IDs</h4>
            <pre>{JSON.stringify(driveRoot.subfolders, null, 2)}</pre>
          </>
        )}
      </div>
      <div className="card">
        <h3>Local Validation</h3>
        <button type="button" onClick={runValidation}>Run Local Validation</button>
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
