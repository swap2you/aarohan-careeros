"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { ToastStack } from "@/components/Toast";
import { authFetch } from "@/lib/api";
import { useToasts } from "@/lib/useToasts";

type Extracted = {
  source: string;
  external_id: string;
  title: string;
  company: string;
  url: string;
  location?: string | null;
  workplace_type?: string | null;
  salary_min?: number | null;
  salary_max?: number | null;
  salary_text?: string | null;
  description_text: string;
  requisition_id?: string | null;
};

type ProfileRec = {
  profile_id: string;
  profile_name: string;
  reason: string;
};

export default function NewOpportunityPage() {
  const router = useRouter();
  const { toasts, push, dismiss } = useToasts();
  const [url, setUrl] = useState("");
  const [plainText, setPlainText] = useState("");
  const [company, setCompany] = useState("");
  const [title, setTitle] = useState("");
  const [location, setLocation] = useState("");
  const [salaryText, setSalaryText] = useState("");
  const [extracted, setExtracted] = useState<Extracted | null>(null);
  const [editableText, setEditableText] = useState("");
  const [profiles, setProfiles] = useState<ProfileRec[]>([]);
  const [selectedProfile, setSelectedProfile] = useState("tpm_delivery");
  const [loading, setLoading] = useState(false);

  async function extract() {
    setLoading(true);
    try {
      const response = await authFetch("/api/opportunities/extract", {
        method: "POST",
        body: JSON.stringify({
          url: url || null,
          plain_text: plainText || null,
          company: company || null,
          title: title || null,
          location: location || null,
          salary_text: salaryText || null,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        push("error", data.detail || "Extraction failed");
        return;
      }
      setExtracted(data.extracted);
      setEditableText(data.editable_text || data.extracted.description_text || "");
      setProfiles(data.recommended_profiles || []);
      if (data.recommended_profiles?.[0]?.profile_id) {
        setSelectedProfile(data.recommended_profiles[0].profile_id);
      }
      push("success", "Review extracted content before confirming.");
    } finally {
      setLoading(false);
    }
  }

  async function confirm(generatePacket: boolean) {
    if (!extracted) return;
    setLoading(true);
    try {
      const payload = {
        extracted: { ...extracted, description_text: editableText },
        resume_profile: selectedProfile,
        generate_packet: generatePacket,
      };
      const response = await authFetch("/api/opportunities/confirm", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) {
        push("error", data.detail || "Could not create opportunity");
        return;
      }
      push("success", `Created job #${data.job_id}`);
      router.push(`/jobs/${data.job_id}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <ToastStack toasts={toasts} onDismiss={dismiss} />
      <h1>New Opportunity</h1>
      <p>Paste a job URL, description, or manual details. Confirm extracted content before creating a job.</p>

      <div className="card">
        <label>Official job URL</label>
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://..." />
        <label>Company</label>
        <input value={company} onChange={(e) => setCompany(e.target.value)} />
        <label>Title</label>
        <input value={title} onChange={(e) => setTitle(e.target.value)} />
        <label>Location</label>
        <input value={location} onChange={(e) => setLocation(e.target.value)} />
        <label>Salary (text)</label>
        <input value={salaryText} onChange={(e) => setSalaryText(e.target.value)} placeholder="$150,000 - $180,000" />
        <label>Pasted job description</label>
        <textarea rows={10} value={plainText} onChange={(e) => setPlainText(e.target.value)} />
        <div className="actions">
          <button type="button" disabled={loading} onClick={() => extract()}>
            {loading ? "Working…" : "Extract & Review"}
          </button>
          <Link href="/jobs">Back to jobs</Link>
        </div>
      </div>

      {extracted && (
        <div className="card">
          <h2>Review before create</h2>
          <p>
            <strong>{extracted.company}</strong> — {extracted.title}
          </p>
          <p className="muted">
            Source: {extracted.source} · Location: {extracted.location || "—"} · Work mode:{" "}
            {extracted.workplace_type || "—"} · Salary:{" "}
            {extracted.salary_min
              ? `$${extracted.salary_min.toLocaleString()}${extracted.salary_max ? ` – $${extracted.salary_max.toLocaleString()}` : ""}`
              : "Not disclosed"}
          </p>
          <label>Editable description (required)</label>
          <textarea rows={12} value={editableText} onChange={(e) => setEditableText(e.target.value)} />
          <label>Recommended resume profile</label>
          <select value={selectedProfile} onChange={(e) => setSelectedProfile(e.target.value)}>
            {profiles.map((p) => (
              <option key={p.profile_id} value={p.profile_id}>
                {p.profile_name}
              </option>
            ))}
            <option value="tpm_delivery">Technical Project / Program Manager</option>
            <option value="qe_manager">QE Manager</option>
            <option value="director_qe">Director-targeted QE</option>
            <option value="platform_architect">Principal / Architect</option>
            <option value="qe_leadership">QE Leadership</option>
            <option value="ai_enabled_qe">AI-Enabled QE</option>
          </select>
          {profiles[0]?.reason && <p className="muted">{profiles[0].reason}</p>}
          <div className="actions">
            <button type="button" disabled={loading || !editableText.trim()} onClick={() => confirm(false)}>
              Create job only
            </button>
            <button type="button" disabled={loading || !editableText.trim()} onClick={() => confirm(true)}>
              Create job + generate packet
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
