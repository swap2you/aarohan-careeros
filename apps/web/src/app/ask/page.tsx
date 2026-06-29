"use client";

import { useState } from "react";
import { authFetch } from "@/lib/api";

type AskResponse = {
  answer: string;
  citations: Array<{ type: string; id: string }>;
  uncertainty: string | null;
};

export default function AskPage() {
  const [question, setQuestion] = useState("How many jobs are in the pipeline?");
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [error, setError] = useState("");

  async function ask() {
    setError("");
    setAudioUrl(null);
    const res = await authFetch("/api/ask", {
      method: "POST",
      body: JSON.stringify({ question }),
    });
    const data = await res.json();
    if (!res.ok) {
      setError(data.detail || "Ask failed");
      return;
    }
    setResponse(data);
  }

  async function speak() {
    if (!response?.answer) return;
    const res = await authFetch("/api/tts", {
      method: "POST",
      body: JSON.stringify({ text: response.answer }),
    });
    const data = await res.json();
    if (data.mode === "generated" || data.mode === "cache") {
      const digest = data.path.split("tts_").pop()?.replace(".mp3", "");
      if (!digest) return;
      const audioRes = await authFetch(`/api/tts/file/${digest}`);
      if (!audioRes.ok) {
        setError("Could not load audio");
        return;
      }
      const blob = await audioRes.blob();
      setAudioUrl(URL.createObjectURL(blob));
    } else {
      setError(data.message || "TTS unavailable — read the answer below.");
    }
  }

  return (
    <div>
      <h1>Ask Aarohan</h1>
      <p>Read-only answers over your jobs, applications, companies, interviews, and Gmail signals.</p>
      <label htmlFor="ask-question">Question</label>
      <textarea id="ask-question" rows={3} value={question} onChange={(e) => setQuestion(e.target.value)} />
      <div className="actions">
        <button type="button" onClick={ask}>Ask</button>
        {response && <button type="button" onClick={speak}>Read aloud</button>}
      </div>
      {error && <p className="error">{error}</p>}
      {response && (
        <div className="card">
          <p>{response.answer}</p>
          {response.uncertainty && <p className="warn">Uncertainty: {response.uncertainty}</p>}
          {response.citations.length > 0 && (
            <>
              <h3>Sources</h3>
              <ul>
                {response.citations.map((c) => (
                  <li key={`${c.type}-${c.id}`}>{c.type} {c.id}</li>
                ))}
              </ul>
            </>
          )}
          {audioUrl && <audio controls src={audioUrl} />}
        </div>
      )}
    </div>
  );
}
