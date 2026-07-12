"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { authFetch, authJson } from "@/lib/api";

type Policy = Record<string, unknown>;

type RoleProfile = { id: string; label?: string; eligibility?: string };

type PolicyVersion = {
  id: number;
  version: number;
  status: string;
  preset: string | null;
  label: string | null;
  notes: string | null;
  overrides: Record<string, unknown>;
  created_by: string | null;
  created_at: string | null;
  activated_by: string | null;
  activated_at: string | null;
};

type PreviewResult = {
  sample_size: number;
  counts: Record<string, number>;
  before_counts: Record<string, number>;
  delta: Record<string, number>;
  examples: Record<string, { id: number; title: string; company: string; decision: string }[]>;
  changed_count: number;
};

type SourceEntry = Record<string, unknown>;
type Inventory = {
  gmail_integration?: { account_email?: string | null; oauth_health?: string };
  email_alert_sources?: SourceEntry[];
  public_sources?: SourceEntry[];
  ats_sources?: SourceEntry[];
};

type RunRow = {
  id: number;
  provider: string;
  started_at: string | null;
  health_state: string | null;
  fetched: number | null;
  accepted: number | null;
  rejected: number | null;
};

const FRESHNESS_OPTIONS = [3, 7, 14, 30];
const ALL_TIERS = ["TODAY", "FRESH", "RECENT", "HISTORICAL"];
const GEO_ACTIONS = ["accept", "owner_review", "reject"];
const GMAIL_SOURCES = [
  ["linkedin_alert_emails", "LinkedIn"],
  ["indeed_alert_emails", "Indeed"],
  ["dice_alert_emails", "Dice"],
  ["usajobs_alert_emails", "USAJOBS"],
  ["glassdoor_alert_emails", "Glassdoor"],
];
const PUBLIC_PROVIDERS = ["adzuna", "jooble", "usajobs", "remotive", "remote_ok", "rss"];

type FormState = {
  freshness_days: number;
  visible_tiers: string[];
  include_secondary: boolean;
  remote_us: string;
  remote_unspecified: string;
  salary_target_usd: number;
  salary_strong_usd: number;
  owner_review_sensitivity: string;
  providers: Record<string, boolean>;
  gmail_sources: Record<string, boolean>;
  primary_families: Record<string, boolean>;
  title_include: string;
  title_exclude: string;
  domain_exclude: string;
  local_hybrid: string;
};

function csvToList(value: string): string[] {
  return value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function num(policy: Policy, path: string[], fallback: number): number {
  let cur: unknown = policy;
  for (const key of path) {
    if (cur && typeof cur === "object") cur = (cur as Record<string, unknown>)[key];
    else return fallback;
  }
  return typeof cur === "number" ? cur : fallback;
}

export default function JobDiscoveryPage() {
  const [effective, setEffective] = useState<Policy | null>(null);
  const [defaults, setDefaults] = useState<Policy | null>(null);
  const [active, setActive] = useState<PolicyVersion | null>(null);
  const [versions, setVersions] = useState<PolicyVersion[]>([]);
  const [inventory, setInventory] = useState<Inventory | null>(null);
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState<FormState>({
    freshness_days: 7,
    visible_tiers: ["TODAY", "FRESH", "RECENT"],
    include_secondary: true,
    remote_us: "accept",
    remote_unspecified: "owner_review",
    salary_target_usd: 200000,
    salary_strong_usd: 170000,
    owner_review_sensitivity: "balanced",
    providers: {},
    gmail_sources: {},
    primary_families: {},
    title_include: "",
    title_exclude: "",
    domain_exclude: "",
    local_hybrid: "",
  });

  const roleProfiles: RoleProfile[] = useMemo(() => {
    const list = (defaults?.["role_profiles"] as RoleProfile[]) || [];
    return list.filter((p) => p.eligibility === "primary");
  }, [defaults]);

  const loadAll = useCallback(async () => {
    try {
      const [eff, def, act, vers, inv, runsData] = await Promise.all([
        authJson<{ policy: Policy }>("/api/discovery/policy/effective"),
        authJson<{ policy: Policy }>("/api/discovery/policy/defaults"),
        authJson<{ active: PolicyVersion | null }>("/api/discovery/policy/active"),
        authJson<{ versions: PolicyVersion[] }>("/api/discovery/policy/versions"),
        authJson<Inventory>("/api/discovery/sources"),
        authJson<{ runs: RunRow[] }>("/api/discovery/runs?limit=20"),
      ]);
      setEffective(eff.policy);
      setDefaults(def.policy);
      setActive(act.active);
      setVersions(vers.versions);
      setInventory(inv);
      setRuns(runsData.runs);
      hydrateForm(eff.policy, act.active);
    } catch (e) {
      setMessage(`Could not load discovery config: ${(e as Error).message}`);
    }
  }, []);

  function hydrateForm(policy: Policy, activeVersion: PolicyVersion | null) {
    const providers: Record<string, boolean> = {};
    const sources = (policy["sources"] as Record<string, { enabled?: boolean }>) || {};
    for (const key of PUBLIC_PROVIDERS) providers[key] = Boolean(sources[key]?.enabled);
    const gmail: Record<string, boolean> = {};
    for (const [key] of GMAIL_SOURCES) gmail[key] = Boolean(sources[key]?.enabled);
    const families: Record<string, boolean> = {};
    for (const p of (policy["role_profiles"] as RoleProfile[]) || []) {
      if (p.eligibility === "primary") families[p.id] = true;
    }
    const ov = (activeVersion?.overrides || {}) as Record<string, unknown>;
    setForm((prev) => ({
      ...prev,
      freshness_days: Math.round(num(policy, ["freshness", "recent_hours"], 168) / 24) || 7,
      visible_tiers: ((policy["freshness"] as Record<string, string[]>)?.default_visible_tiers) || ["TODAY", "FRESH", "RECENT"],
      remote_us: ((policy["geography"] as Record<string, string>)?.remote_us) || "accept",
      remote_unspecified: ((policy["geography"] as Record<string, string>)?.remote_unspecified) || "owner_review",
      salary_target_usd: num(policy, ["salary", "target_max_usd"], 200000),
      salary_strong_usd: num(policy, ["salary", "strong_max_usd"], 170000),
      include_secondary: ov["include_secondary"] !== false,
      owner_review_sensitivity: (ov["owner_review_sensitivity"] as string) || "balanced",
      providers,
      gmail_sources: gmail,
      primary_families: families,
    }));
  }

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  function buildOverrides(): Record<string, unknown> {
    const overrides: Record<string, unknown> = {
      freshness_days: form.freshness_days,
      visible_tiers: form.visible_tiers,
      include_secondary: form.include_secondary,
      remote_us: form.remote_us,
      remote_unspecified: form.remote_unspecified,
      salary_target_usd: form.salary_target_usd,
      salary_strong_usd: form.salary_strong_usd,
      owner_review_sensitivity: form.owner_review_sensitivity,
      providers: form.providers,
      gmail_sources: form.gmail_sources,
      primary_families: form.primary_families,
    };
    if (csvToList(form.title_include).length) overrides.title_include = csvToList(form.title_include);
    if (csvToList(form.title_exclude).length) overrides.title_exclude = csvToList(form.title_exclude);
    if (csvToList(form.domain_exclude).length) overrides.domain_exclude = csvToList(form.domain_exclude);
    if (csvToList(form.local_hybrid).length) overrides.local_hybrid = csvToList(form.local_hybrid);
    return overrides;
  }

  async function applyPreset(name: string) {
    try {
      const data = await authJson<{ presets: { name: string; overrides: Record<string, unknown> }[] }>(
        "/api/discovery/presets",
      );
      const preset = data.presets.find((p) => p.name === name);
      const ov = preset?.overrides || {};
      setForm((prev) => ({
        ...prev,
        freshness_days: (ov.freshness_days as number) ?? (name === "strict" ? 3 : name === "broad" ? 14 : 7),
        visible_tiers: (ov.visible_tiers as string[]) ?? ["TODAY", "FRESH", "RECENT"],
        include_secondary: (ov.include_secondary as boolean) ?? name !== "strict",
        remote_unspecified: (ov.remote_unspecified as string) ?? "owner_review",
        owner_review_sensitivity: (ov.owner_review_sensitivity as string) ?? "balanced",
      }));
      setMessage(`Loaded "${name}" preset into the form. Preview, then save & activate.`);
    } catch (e) {
      setMessage(`Preset load failed: ${(e as Error).message}`);
    }
  }

  async function runPreview() {
    setBusy(true);
    setMessage("Computing preview against recent records…");
    try {
      const result = await authJson<PreviewResult>("/api/discovery/policy/preview", {
        method: "POST",
        body: JSON.stringify({ overrides: buildOverrides(), sample_limit: 6 }),
      });
      setPreview(result);
      setMessage(`Preview ready (${result.sample_size} records evaluated).`);
    } catch (e) {
      setMessage(`Preview failed: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  async function saveAndActivate() {
    setBusy(true);
    try {
      const draft = await authJson<{ version: PolicyVersion }>("/api/discovery/policy/draft", {
        method: "POST",
        body: JSON.stringify({ overrides: buildOverrides(), label: "Owner edit", preset: null }),
      });
      await authJson("/api/discovery/policy/" + draft.version.id + "/activate", { method: "POST" });
      setMessage(`Activated policy v${draft.version.version}.`);
      await loadAll();
    } catch (e) {
      setMessage(`Save/activate failed: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  async function activateExisting(id: number) {
    setBusy(true);
    try {
      await authJson("/api/discovery/policy/" + id + "/activate", { method: "POST" });
      setMessage("Version activated.");
      await loadAll();
    } catch (e) {
      setMessage(`Activate failed: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  async function restoreDefaults() {
    if (!window.confirm("Restore discovery defaults? This activates a defaults-only policy version.")) return;
    setBusy(true);
    try {
      await authJson("/api/discovery/policy/restore-defaults", { method: "POST" });
      setMessage("Defaults restored.");
      await loadAll();
    } catch (e) {
      setMessage(`Restore failed: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  async function runDiscovery(path: string, label: string) {
    setBusy(true);
    setMessage(`${label}…`);
    try {
      const res = await authFetch(path, { method: "POST", body: JSON.stringify({ use_fixture: false }) });
      const data = await res.json();
      setMessage(`${label}: ${data.message || JSON.stringify(data.totals || data)}`);
      await loadAll();
    } catch (e) {
      setMessage(`${label} failed: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  function toggleTier(tier: string) {
    setForm((prev) => ({
      ...prev,
      visible_tiers: prev.visible_tiers.includes(tier)
        ? prev.visible_tiers.filter((t) => t !== tier)
        : [...prev.visible_tiers, tier],
    }));
  }

  return (
    <div>
      <h1>Job Discovery</h1>
      <p className="muted">
        Discovery Control Center — configure sources, criteria, and freshness; preview impact
        before activating. Application defaults are immutable; owner changes are versioned in the
        database and can be rolled back.
      </p>

      {/* A. Active policy summary */}
      <div className="card">
        <h3>Active policy</h3>
        <p>
          <strong>Version:</strong> {active ? `v${active.version}${active.preset ? ` (${active.preset})` : ""}` : "Defaults (no owner override)"}
          {active?.activated_at ? ` · activated ${new Date(active.activated_at).toLocaleString()}` : ""}
        </p>
        {effective && (
          <ul>
            <li>Freshness window: {Math.round(num(effective, ["freshness", "recent_hours"], 168) / 24)} days</li>
            <li>Visible tiers: {((effective["freshness"] as Record<string, string[]>)?.default_visible_tiers || []).join(", ")}</li>
            <li>Geography: {(effective["geography"] as Record<string, string>)?.country} · remote {(effective["geography"] as Record<string, string>)?.remote_us} · unspecified {(effective["geography"] as Record<string, string>)?.remote_unspecified} · foreign {(effective["geography"] as Record<string, string>)?.foreign_only}</li>
            <li>Salary bands: target ${num(effective, ["salary", "target_max_usd"], 0).toLocaleString()} · strong ${num(effective, ["salary", "strong_max_usd"], 0).toLocaleString()}</li>
            <li>Reject patterns: {((effective["role_reject_patterns"] as string[]) || []).length} · Domain exclusions: {((effective["domain_reject_patterns"] as string[]) || []).length}</li>
          </ul>
        )}
      </div>

      {/* Presets */}
      <div className="card">
        <h3>Presets</h3>
        <p className="muted">Broad is wider, never unfiltered — foreign-only, clearly unrelated, and fixture/test rows always stay excluded.</p>
        <div className="actions">
          <button type="button" onClick={() => applyPreset("strict")} disabled={busy}>Strict</button>
          <button type="button" onClick={() => applyPreset("balanced")} disabled={busy}>Balanced (default)</button>
          <button type="button" onClick={() => applyPreset("broad")} disabled={busy}>Broad</button>
        </div>
      </div>

      {/* B. Editable owner settings */}
      <div className="card">
        <h3>Editable settings</h3>
        <p>
          <strong>Freshness window:</strong>{" "}
          <select value={form.freshness_days} onChange={(e) => setForm({ ...form, freshness_days: Number(e.target.value) })}>
            {FRESHNESS_OPTIONS.map((d) => (
              <option key={d} value={d}>{d} days</option>
            ))}
          </select>
        </p>
        <p>
          <strong>Visible tiers:</strong>{" "}
          {ALL_TIERS.map((t) => (
            <label key={t} style={{ marginRight: 12 }}>
              <input type="checkbox" checked={form.visible_tiers.includes(t)} onChange={() => toggleTier(t)} /> {t}
            </label>
          ))}
        </p>
        <p>
          <label>
            <input type="checkbox" checked={form.include_secondary} onChange={(e) => setForm({ ...form, include_secondary: e.target.checked })} />{" "}
            Include secondary role families
          </label>
        </p>
        <p>
          <strong>Primary role families:</strong>
        </p>
        <div>
          {roleProfiles.map((p) => (
            <label key={p.id} style={{ display: "inline-block", marginRight: 14 }}>
              <input
                type="checkbox"
                checked={form.primary_families[p.id] !== false}
                onChange={(e) => setForm({ ...form, primary_families: { ...form.primary_families, [p.id]: e.target.checked } })}
              />{" "}
              {p.label || p.id}
            </label>
          ))}
        </div>
        <p>
          <strong>US remote:</strong>{" "}
          <select value={form.remote_us} onChange={(e) => setForm({ ...form, remote_us: e.target.value })}>
            {GEO_ACTIONS.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>{" "}
          <strong>Remote unspecified:</strong>{" "}
          <select value={form.remote_unspecified} onChange={(e) => setForm({ ...form, remote_unspecified: e.target.value })}>
            {GEO_ACTIONS.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </p>
        <p className="muted">Foreign-only and relocation-required always stay rejected and cannot be enabled here.</p>
        <p>
          <strong>Salary target $:</strong>{" "}
          <input type="number" value={form.salary_target_usd} onChange={(e) => setForm({ ...form, salary_target_usd: Number(e.target.value) })} />{" "}
          <strong>Strong band $:</strong>{" "}
          <input type="number" value={form.salary_strong_usd} onChange={(e) => setForm({ ...form, salary_strong_usd: Number(e.target.value) })} />
          <span className="muted"> (ranking/review only — never a hard reject)</span>
        </p>
        <p>
          <strong>Local / hybrid locations (comma separated):</strong><br />
          <input style={{ width: "100%" }} value={form.local_hybrid} onChange={(e) => setForm({ ...form, local_hybrid: e.target.value })} placeholder="Harrisburg, Lancaster, …" />
        </p>
        <p>
          <strong>Title include phrases:</strong><br />
          <input style={{ width: "100%" }} value={form.title_include} onChange={(e) => setForm({ ...form, title_include: e.target.value })} placeholder="e.g. quality platform lead" />
        </p>
        <p>
          <strong>Title exclude phrases:</strong><br />
          <input style={{ width: "100%" }} value={form.title_exclude} onChange={(e) => setForm({ ...form, title_exclude: e.target.value })} placeholder="added to reject patterns" />
        </p>
        <p>
          <strong>Domain exclusion phrases:</strong><br />
          <input style={{ width: "100%" }} value={form.domain_exclude} onChange={(e) => setForm({ ...form, domain_exclude: e.target.value })} placeholder="added to domain rejects" />
        </p>
        <p>
          <strong>Providers:</strong>{" "}
          {PUBLIC_PROVIDERS.map((key) => (
            <label key={key} style={{ marginRight: 12 }}>
              <input
                type="checkbox"
                checked={Boolean(form.providers[key])}
                onChange={(e) => setForm({ ...form, providers: { ...form.providers, [key]: e.target.checked } })}
              />{" "}
              {key}
            </label>
          ))}
        </p>
        <p>
          <strong>Gmail alert sources:</strong>{" "}
          {GMAIL_SOURCES.map(([key, label]) => (
            <label key={key} style={{ marginRight: 12 }}>
              <input
                type="checkbox"
                checked={Boolean(form.gmail_sources[key])}
                onChange={(e) => setForm({ ...form, gmail_sources: { ...form.gmail_sources, [key]: e.target.checked } })}
              />{" "}
              {label}
            </label>
          ))}
        </p>
        <p>
          <strong>Owner-review sensitivity:</strong>{" "}
          <select value={form.owner_review_sensitivity} onChange={(e) => setForm({ ...form, owner_review_sensitivity: e.target.value })}>
            {["strict", "balanced", "broad"].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </p>
        <div className="actions">
          <button type="button" onClick={runPreview} disabled={busy}>Preview impact</button>
          <button type="button" onClick={saveAndActivate} disabled={busy}>Save & activate</button>
          <button type="button" onClick={restoreDefaults} disabled={busy}>Restore defaults</button>
        </div>
      </div>

      {/* D. Preview */}
      {preview && (
        <div className="card">
          <h3>Preview impact ({preview.sample_size} records)</h3>
          <table className="data-table">
            <thead>
              <tr><th>Group</th><th>Before</th><th>After</th><th>Delta</th></tr>
            </thead>
            <tbody>
              {["would_accept", "would_owner_review", "would_quarantine", "would_reject"].map((k) => (
                <tr key={k}>
                  <td>{k.replace("would_", "").replace("_", " ")}</td>
                  <td>{preview.before_counts[k] ?? 0}</td>
                  <td>{preview.counts[k] ?? 0}</td>
                  <td>{(preview.delta[k] ?? 0) > 0 ? `+${preview.delta[k]}` : preview.delta[k]}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted">{preview.changed_count} records would change decision.</p>
          {preview.examples.would_accept?.length > 0 && (
            <p className="muted">Accept examples: {preview.examples.would_accept.map((e) => `${e.title} @ ${e.company}`).join("; ")}</p>
          )}
        </div>
      )}

      {/* Run discovery */}
      <div className="card">
        <h3>Run discovery</h3>
        <p className="muted">Gmail alerts are a separate stage from public feeds and are never silently folded in.</p>
        <div className="actions">
          <button type="button" onClick={() => runDiscovery("/api/discovery/run", "Run All Discovery")} disabled={busy}>Run All Discovery</button>
          <button type="button" onClick={() => runDiscovery("/api/discovery/run/gmail", "Sync Gmail Alerts")} disabled={busy}>Sync Gmail Alerts</button>
          <button type="button" onClick={() => runDiscovery("/api/discovery/run/public", "Run Public Sources")} disabled={busy}>Run Public Sources</button>
          <button type="button" onClick={loadAll} disabled={busy}>Review Source Status</button>
        </div>
      </div>

      {/* Diagnostics: source status */}
      {inventory && (
        <div className="card">
          <h3>Source status</h3>
          <p>
            <strong>Gmail integration:</strong> {inventory.gmail_integration?.oauth_health || "—"}
            {inventory.gmail_integration?.account_email ? ` · ${inventory.gmail_integration.account_email}` : ""}
          </p>
          <h4>Email alert sources (not public-feed connectors)</h4>
          <table className="data-table">
            <thead><tr><th>Source</th><th>Enabled</th><th>Credentials</th><th>OAuth</th><th>Orchestration</th></tr></thead>
            <tbody>
              {(inventory.email_alert_sources || []).map((s, i) => (
                <tr key={i}>
                  <td>{String(s.label)}</td>
                  <td>{s.enabled_in_policy ? "Yes" : "No"}</td>
                  <td>{s.credentials_present ? "Yes" : "No"}</td>
                  <td>{String(s.oauth_health ?? "—")}</td>
                  <td>{String(s.orchestration ?? "—")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <h4>Public / API sources</h4>
          <table className="data-table">
            <thead><tr><th>Source</th><th>Enabled</th><th>State</th><th>Last run</th><th>Skip reason</th></tr></thead>
            <tbody>
              {(inventory.public_sources || []).map((s, i) => (
                <tr key={i}>
                  <td>{String(s.source_key)}</td>
                  <td>{s.enabled_in_policy ? "Yes" : "No"}</td>
                  <td>{String(s.connector_state ?? "—")}</td>
                  <td>{s.last_attempted_run ? new Date(String(s.last_attempted_run)).toLocaleString() : "—"}</td>
                  <td>{String(s.skip_reason ?? "—")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <h4>ATS boards</h4>
          <table className="data-table">
            <thead><tr><th>Source</th><th>Enabled</th><th>Approved boards</th><th>Skip reason</th></tr></thead>
            <tbody>
              {(inventory.ats_sources || []).map((s, i) => (
                <tr key={i}>
                  <td>{String(s.source_key)}</td>
                  <td>{s.enabled_in_policy ? "Yes" : "No"}</td>
                  <td>{Number(s.approved_boards_count ?? 0)}</td>
                  <td>{String(s.skip_reason ?? "—")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Diagnostics: last runs */}
      <div className="card">
        <h3>Last discovery runs</h3>
        {runs.length === 0 ? (
          <p className="muted">No connector runs recorded yet.</p>
        ) : (
          <table className="data-table">
            <thead><tr><th>Provider</th><th>Started</th><th>Health</th><th>Fetched</th><th>Accepted</th><th>Rejected</th></tr></thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id}>
                  <td>{r.provider}</td>
                  <td>{r.started_at ? new Date(r.started_at).toLocaleString() : "—"}</td>
                  <td>{r.health_state || "—"}</td>
                  <td>{r.fetched ?? "—"}</td>
                  <td>{r.accepted ?? "—"}</td>
                  <td>{r.rejected ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* E. Governance */}
      <div className="card">
        <h3>Governance & version history</h3>
        {versions.length === 0 ? (
          <p className="muted">No owner policy versions yet — defaults are active.</p>
        ) : (
          <table className="data-table">
            <thead><tr><th>Version</th><th>Status</th><th>Preset</th><th>Changed by</th><th>Changed at</th><th></th></tr></thead>
            <tbody>
              {versions.map((v) => (
                <tr key={v.id}>
                  <td>v{v.version}</td>
                  <td>{v.status}</td>
                  <td>{v.preset || v.label || "—"}</td>
                  <td>{v.activated_by || v.created_by || "—"}</td>
                  <td>{(v.activated_at || v.created_at) ? new Date(v.activated_at || v.created_at || "").toLocaleString() : "—"}</td>
                  <td>
                    {v.status !== "active" && (
                      <button type="button" onClick={() => activateExisting(v.id)} disabled={busy}>Activate</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {message && <p className="status">{message}</p>}
    </div>
  );
}
