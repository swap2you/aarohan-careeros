"use client";

import { useCallback, useEffect, useState } from "react";
import { useDeploymentEnvironment } from "@/components/EnvironmentBadge";
import { authFetch } from "@/lib/api";

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
  google_health_state?: string;
  google_display_status?: string;
  google_remediation?: string | null;
  token_usable?: boolean;
  dedicated_gmail?: string;
  google_health?: {
    last_successful_refresh?: string | null;
    last_drive_check_ok?: boolean;
    last_gmail_check_ok?: boolean;
    remediation?: string | null;
  };
  drive_root?: DriveRoot;
  fixture_mode?: boolean;
};

type ApplicationMode = {
  id: string;
  label: string;
  description: string;
  enabled: boolean;
};

type ValidationStep = {
  name: string;
  status: string;
  summary: string;
  ok?: boolean;
};

type ValidationRun = {
  status?: string;
  summary?: string;
  results?: {
    mode?: string;
    plain_summary?: string;
    steps?: ValidationStep[];
  };
};

function maskId(value: string | null | undefined): string {
  if (!value) return "—";
  if (value.length <= 12) return value;
  return `${value.slice(0, 6)}…${value.slice(-4)}`;
}

function plainError(detail: unknown): string {
  if (!detail) return "Something went wrong. Try again or check Technical Details.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => (typeof d === "object" && d && "msg" in d ? String(d.msg) : String(d))).join(" ");
  }
  if (typeof detail === "object" && detail && "detail" in detail) {
    return plainError((detail as { detail: unknown }).detail);
  }
  return "Something went wrong. Try again or check Technical Details.";
}

export default function SettingsPage() {
  const [status, setStatus] = useState<IntegrationStatus | null>(null);
  const [validation, setValidation] = useState<ValidationRun | null>(null);
  const [applicationModes, setApplicationModes] = useState<ApplicationMode[]>([]);
  const [message, setMessage] = useState("");
  const [technicalOpen, setTechnicalOpen] = useState(false);
  const [validationTechnicalOpen, setValidationTechnicalOpen] = useState(false);

  const { showFixtureControls, environment } = useDeploymentEnvironment();
  const localBypassEnabled = Boolean(environment?.local_dev_auth_bypass && environment?.is_owner_stack);

  const loadStatus = useCallback(() => {
    authFetch(`/api/integrations/status`)
      .then((res) => res.json())
      .then(setStatus)
      .catch(() => setMessage("Could not load Google integration status."));
  }, []);

  useEffect(() => {
    loadStatus();
    authFetch(`/api/validation/latest`)
      .then((res) => res.json())
      .then(setValidation);
    authFetch(`/api/companies/application-modes`)
      .then((res) => res.json())
      .then((data) => setApplicationModes(data.modes || []));
  }, [loadStatus]);

  async function connectGoogle() {
    const response = await authFetch(`/api/integrations/google/connect?service=google&reconnect=true`);
    const data = await response.json();
    if (data.auth_url) window.open(data.auth_url, "_blank");
    else setMessage(data.message || "Google sign-in is not configured on this server.");
  }

  async function disconnectGoogle() {
    const ok = window.confirm(
      "Disconnect Google? Gmail sync and Drive uploads will stop until you reconnect.",
    );
    if (!ok) return;
    await authFetch(`/api/integrations/google/disconnect?service=all`, { method: "POST" });
    setMessage("Google disconnected.");
    loadStatus();
  }

  async function createDriveRoot() {
    setMessage("Creating Aarohan Drive root…");
    const response = await authFetch(`/api/integrations/google/drive/create-root`, { method: "POST" });
    const data = await response.json();
    if (!response.ok) {
      setMessage(plainError(data.detail || data));
      return;
    }
    setMessage("Drive root created and linked.");
    loadStatus();
  }

  async function syncDriveFolders() {
    const response = await authFetch(`/api/integrations/google/drive/folders`);
    const data = await response.json();
    if (!response.ok) {
      setMessage(plainError(data.detail || data));
      return;
    }
    setMessage(`Drive subfolders synced (${Object.keys(data.folders || {}).length} folders).`);
    loadStatus();
  }

  async function syncGmail() {
    setMessage("Syncing Gmail (read-only)…");
    const response = await authFetch(`/api/integrations/gmail/sync`, { method: "POST" });
    const data = await response.json();
    if (!response.ok) {
      setMessage(plainError(data.detail || data));
      return;
    }
    setMessage(
      `Gmail sync complete: ${data.processed ?? 0} processed, ${data.skipped ?? 0} skipped.`,
    );
  }

  async function syncFixtureGmail() {
    const response = await authFetch(`/api/integrations/gmail/sync-fixture`, { method: "POST" });
    const data = await response.json();
    setMessage(`Fixture sync: ${data.processed ?? 0} messages loaded.`);
  }

  async function recreateLocalOwnerSession() {
    setMessage("Recreating local owner session…");
    const response = await authFetch(`/api/auth/local-admin-login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ remember_me: true }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      setMessage(plainError(data.detail || data));
      return;
    }
    setMessage("Local owner session refreshed.");
  }

  async function runValidation() {
    setMessage("Running local validation…");
    const response = await authFetch(`/api/validation/run`, { method: "POST" });
    const data = await response.json();
    setValidation(data);
    setMessage(`Local validation: ${data.status === "PASS" ? "PASS" : "FAIL"}`);
  }

  const driveRoot = status?.drive_root;
  const healthState = status?.google_health_state || (status?.google_connected ? "LINKED_UNVERIFIED" : "DISCONNECTED");
  const showReconnect = healthState === "REAUTH_REQUIRED" || healthState === "DISCONNECTED";
  const showConnect = healthState === "DISCONNECTED";
  const googleHealthy = healthState === "HEALTHY" || healthState === "DEGRADED";
  const showCreateRoot = Boolean(googleHealthy && driveRoot && !driveRoot.accessible);
  const validationSteps = validation?.results?.steps ?? [];
  const validationSummary =
    validation?.results?.plain_summary || validation?.summary || validation?.status || "NONE";

  return (
    <div>
      <h1>Settings & Integrations</h1>
      <div className="card">
        <h3>Local Development</h3>
        <p>
          <strong>App environment:</strong> {environment?.app_env || "—"}
        </p>
        <p>
          <strong>Local admin bypass:</strong> {localBypassEnabled ? "enabled" : "disabled"}
        </p>
        <p className="muted">
          Configuration loads from <code>.env.local</code> only. Secrets are never committed to Git.
        </p>
        {localBypassEnabled && (
          <button onClick={() => void recreateLocalOwnerSession()}>Recreate Local Owner Session</button>
        )}
      </div>
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
        <p>
          <strong>Connected account:</strong> {status?.connected_account || "Not connected"}
        </p>
        <p>
          <strong>Dedicated Gmail:</strong> {status?.dedicated_gmail || "—"}
        </p>
        <p>
          <strong>Status:</strong> {status?.google_display_status || healthState}
          {status?.fixture_mode ? " (fixture mode)" : ""}
        </p>
        {status?.google_remediation && <p className="warn">{status.google_remediation}</p>}
        {status?.google_health?.last_successful_refresh && (
          <p className="muted">Last token refresh: {status.google_health.last_successful_refresh}</p>
        )}
        <div className="actions">
          {showConnect && <button onClick={() => connectGoogle()}>Connect Google</button>}
          {showReconnect && !showConnect && (
            <button onClick={() => connectGoogle()}>Reconnect Google</button>
          )}
          <button onClick={disconnectGoogle}>Disconnect Google</button>
          <button onClick={syncGmail} disabled={!status?.token_usable}>
            Sync Gmail (read-only)
          </button>
          {showFixtureControls && (
            <button onClick={syncFixtureGmail}>Sync Gmail Fixture</button>
          )}
        </div>
      </div>
      <div className="card">
        <h3>Google Drive Root</h3>
        <p>
          <strong>Accessible:</strong> {driveRoot?.accessible ? "Yes" : "No"}
        </p>
        <p>
          <strong>Root source:</strong> {driveRoot?.source || "—"}
        </p>
        {driveRoot?.warning && <p className="error">{driveRoot.warning}</p>}
        {showCreateRoot && (
          <button onClick={createDriveRoot}>Create Aarohan Drive Root</button>
        )}
        <button onClick={syncDriveFolders}>Sync Drive Subfolders</button>
        {driveRoot?.subfolders && Object.keys(driveRoot.subfolders).length > 0 && (
          <p>
            <strong>Subfolders:</strong> {Object.keys(driveRoot.subfolders).join(", ")}
          </p>
        )}
      </div>
      <div className="card">
        <h3>Local Validation</h3>
        <p>
          <strong>Result:</strong>{" "}
          <span className={
            validation?.status === "PASS" ? "status-pass"
            : validation?.status === "FAIL" ? "error"
            : ""
          }>
            {validation?.status || "NONE"}
          </span>
        </p>
        <p>{validationSummary}</p>
        {validationSteps.length > 0 && (
          <ul>
            {validationSteps.map((step) => (
              <li key={step.name}>
                <strong>{step.name}:</strong> {step.status} — {step.summary}
              </li>
            ))}
          </ul>
        )}
        <button onClick={runValidation}>Run Local Validation</button>
        {validation && (
          <details
            open={validationTechnicalOpen}
            onToggle={(e) => setValidationTechnicalOpen((e.target as HTMLDetailsElement).open)}
          >
            <summary>Technical Details</summary>
            <pre>{JSON.stringify(validation, null, 2)}</pre>
          </details>
        )}
      </div>
      {message && <p className="status">{message}</p>}
      <div className="card">
        <p>Human approval is required before external submission or messaging.</p>
      </div>
      {status && (
        <details
          open={technicalOpen}
          onToggle={(e) => setTechnicalOpen((e.target as HTMLDetailsElement).open)}
        >
          <summary>Technical Details (integration status)</summary>
          <p>
            <strong>Configured root:</strong> {maskId(driveRoot?.configured_folder_id)}
          </p>
          <p>
            <strong>Active root:</strong> {maskId(driveRoot?.active_folder_id)}
          </p>
          <pre>{JSON.stringify(status, null, 2)}</pre>
        </details>
      )}
    </div>
  );
}
