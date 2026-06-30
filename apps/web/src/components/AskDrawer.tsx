"use client";

import { usePathname } from "next/navigation";
import { useMemo, useState } from "react";

import { ToastStack } from "@/components/Toast";
import { authFetch } from "@/lib/api";
import { useToasts } from "@/lib/useToasts";

type AskResponse = {
  answer: string;
  citations: Array<{ type: string; id: string }>;
  uncertainty: string | null;
};

const SUGGESTED = [
  "Why does this job match me?",
  "What are my gaps?",
  "Have I applied to this company?",
  "Which resume should I use?",
  "Summarize this job.",
  "What needs my attention today?",
];

export function AskDrawer() {
  const pathname = usePathname();
  const { toasts, push, dismiss } = useToasts();
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [history, setHistory] = useState<Array<{ q: string; a: AskResponse }>>([]);

  const contextHint = useMemo(() => {
    const jobMatch = pathname.match(/^\/jobs\/(\d+)/);
    const appMatch = pathname.match(/^\/applications/);
    if (jobMatch) return { job_id: Number(jobMatch[1]) };
    if (appMatch) return { page: "applications" };
    return { page: pathname.replace(/^\//, "") || "overview" };
  }, [pathname]);

  async function ask(customQuestion?: string) {
    const q = (customQuestion ?? question).trim();
    if (!q) return;
    setLoading(true);
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
      push("success", "Answer ready");
    } finally {
      setLoading(false);
    }
  }

  if (pathname === "/login") return null;

  return (
    <>
      <ToastStack toasts={toasts} onDismiss={dismiss} />
      <button type="button" className="ask-fab" onClick={() => setOpen(true)} aria-label="Ask Aarohan">
        Ask Aarohan
      </button>
      {open && (
        <div className="ask-drawer-backdrop" onClick={() => setOpen(false)} role="presentation">
          <aside
            className="ask-drawer"
            onClick={(e) => e.stopPropagation()}
            aria-label="Ask Aarohan assistant"
          >
            <header>
              <h2>Ask Aarohan</h2>
              <button type="button" onClick={() => setOpen(false)}>
                Close
              </button>
            </header>
            <p className="muted">Context: {JSON.stringify(contextHint)}</p>
            <div className="suggested-prompts">
              {SUGGESTED.map((s) => (
                <button key={s} type="button" disabled={loading} onClick={() => ask(s)}>
                  {s}
                </button>
              ))}
            </div>
            <label htmlFor="ask-drawer-question">Your question</label>
            <textarea
              id="ask-drawer-question"
              rows={3}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />
            <div className="actions">
              <button type="button" disabled={loading} onClick={() => ask()}>
                {loading ? "Thinking…" : "Ask"}
              </button>
              {loading && (
                <button type="button" onClick={() => setLoading(false)}>
                  Stop
                </button>
              )}
            </div>
            {response && (
              <div className="card">
                <p>{response.answer}</p>
                {response.uncertainty && <p className="warn">Uncertainty: {response.uncertainty}</p>}
                {response.citations.length > 0 && (
                  <ul>
                    {response.citations.map((c) => (
                      <li key={`${c.type}-${c.id}`}>
                        {c.type} {c.id}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
            {history.length > 0 && (
              <>
                <h3>Recent</h3>
                <ul>
                  {history.map((h) => (
                    <li key={h.q}>
                      <strong>{h.q}</strong>
                      <br />
                      {h.a.answer.slice(0, 160)}…
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
