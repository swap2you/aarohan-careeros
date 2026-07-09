"use client";

import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { ToastStack } from "@/components/Toast";
import { authFetch } from "@/lib/api";
import { useToasts } from "@/lib/useToasts";

type AskResponse = {
  answer: string;
  citations: Array<{ type: string; id: string }>;
  uncertainty: string | null;
  mode?: string;
};

type AskDrawerProps = {
  open: boolean;
  onOpen: () => void;
  onClose: () => void;
};

function contextLabel(context: Record<string, unknown>): string {
  if (context.job_id) return `Job #${context.job_id}`;
  if (context.application_id) return `Application #${context.application_id}`;
  const page = String(context.page || "overview");
  return page.replace(/-/g, " ");
}

export function AskDrawer({ open, onOpen, onClose }: AskDrawerProps) {
  const pathname = usePathname();
  const { toasts, push, dismiss } = useToasts();
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [history, setHistory] = useState<Array<{ q: string; a: AskResponse }>>([]);

  const contextHint = useMemo(() => {
    const jobMatch = pathname.match(/^\/jobs\/(\d+)/);
    const appMatch = pathname.match(/^\/applications/);
    if (jobMatch) return { job_id: Number(jobMatch[1]), page: "job_detail" };
    if (appMatch) return { page: "applications" };
    return { page: pathname.replace(/^\//, "") || "overview" };
  }, [pathname]);

  const suggested = useMemo(() => {
    if (contextHint.job_id) {
      return [
        "Summarize this job and its fit score",
        "What are my gaps for this role?",
        "Have I applied to this company before?",
        "What salary range is listed?",
      ];
    }
    return [
      "How many jobs are in the pipeline?",
      "Which applications need my attention?",
      "What is the average salary in my pipeline?",
      "Summarize recent Gmail signals",
    ];
  }, [contextHint.job_id]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  async function ask(customQuestion?: string) {
    const q = (customQuestion ?? question).trim();
    if (!q) return;
    setLoading(true);
    setQuestion(q);
    try {
      const res = await authFetch("/api/ask", {
        method: "POST",
        body: JSON.stringify({ question: q, context: contextHint }),
      });
      const data = await res.json();
      if (!res.ok) {
        push("error", data.detail || "Ask failed");
        return;
      }
      setResponse(data);
      setHistory((h) => [...h.slice(-4), { q, a: data }]);
    } finally {
      setLoading(false);
    }
  }

  if (pathname === "/login") return null;

  return (
    <>
      <ToastStack toasts={toasts} onDismiss={dismiss} />
      <button
        type="button"
        className="ask-fab"
        onClick={() => (open ? onClose() : onOpen())}
        aria-label="Ask Aarohan AI assistant"
        aria-expanded={open}
      >
        <span className="ask-fab-icon" aria-hidden="true">
          ✦
        </span>
        <span className="ask-fab-label">Ask Aarohan</span>
      </button>
      {open && (
        <div className="ask-drawer-backdrop" onClick={onClose} role="presentation">
          <aside
            className="ask-drawer"
            onClick={(e) => e.stopPropagation()}
            aria-label="Ask Aarohan assistant"
          >
            <header className="ask-drawer-header">
              <div>
                <p className="eyebrow">AI agent</p>
                <h2>Ask Aarohan</h2>
                <p className="muted ask-context-pill">
                  Context: <strong>{contextLabel(contextHint)}</strong>
                </p>
              </div>
              <button type="button" className="ask-close" onClick={onClose} aria-label="Close">
                ×
              </button>
            </header>
            <p className="muted ask-intro">
              Answers come from your CareerOS database — jobs, applications, companies, interviews,
              and Gmail signals. Off-topic questions are declined.
            </p>
            <div className="suggested-prompts">
              {suggested.map((s) => (
                <button key={s} type="button" className="chip-btn" disabled={loading} onClick={() => ask(s)}>
                  {s}
                </button>
              ))}
            </div>
            <label htmlFor="ask-drawer-question">Your question</label>
            <textarea
              id="ask-drawer-question"
              rows={4}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. Which jobs pay over $150k?"
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault();
                  void ask();
                }
              }}
            />
            <div className="actions">
              <button type="button" disabled={loading} onClick={() => void ask()}>
                {loading ? "Analyzing…" : "Ask"}
              </button>
            </div>
            {response && (
              <div className="card ask-answer-card">
                {response.mode && <p className="ask-mode-tag">{response.mode}</p>}
                <p className="ask-answer-text">{response.answer}</p>
                {response.uncertainty && (
                  <p className="warn">Note: {response.uncertainty.replace(/_/g, " ")}</p>
                )}
                {response.citations.length > 0 && (
                  <>
                    <h3>Sources</h3>
                    <ul className="ask-citations">
                      {response.citations.map((c) => (
                        <li key={`${c.type}-${c.id}`}>
                          <span className="citation-type">{c.type}</span> {c.id}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            )}
            {history.length > 1 && (
              <>
                <h3>Recent</h3>
                <ul className="ask-history">
                  {history.slice(0, -1).map((h) => (
                    <li key={h.q}>
                      <button type="button" className="chip-btn" onClick={() => ask(h.q)}>
                        {h.q}
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </aside>
        </div>
      )}
    </>
  );
}
