"use client";

import { useCallback, useRef, useState } from "react";

import { authFetch } from "@/lib/api";

type Props = {
  text: string;
  label?: string;
};

export function TtsMiniPlayer({ text, label = "Document" }: Props) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "playing" | "paused" | "error">("idle");
  const [error, setError] = useState("");
  const [speed, setSpeed] = useState(1);
  const [src, setSrc] = useState<string | null>(null);

  const loadAudio = useCallback(async () => {
    if (!text.trim()) return null;
    setStatus("loading");
    setError("");
    const res = await authFetch("/api/tts", { method: "POST", body: JSON.stringify({ text }) });
    const data = await res.json();
    if (data.mode !== "generated" && data.mode !== "cache") {
      setStatus("error");
      setError(data.message || "OpenAI TTS unavailable. Start stack via Start-Aarohan.ps1 with AI_API_KEY.");
      return null;
    }
    const digest = data.path.split("tts_").pop()?.replace(".mp3", "");
    if (!digest) {
      setStatus("error");
      setError("Invalid TTS response");
      return null;
    }
    const audioRes = await authFetch(`/api/tts/file/${digest}`);
    if (!audioRes.ok) {
      setStatus("error");
      setError("Could not load audio file");
      return null;
    }
    const blob = await audioRes.blob();
    const url = URL.createObjectURL(blob);
    setSrc(url);
    return url;
  }, [text]);

  async function play() {
    let url = src;
    if (!url) url = await loadAudio();
    if (!url) return;
    if (!audioRef.current) {
      audioRef.current = new Audio(url);
      audioRef.current.onended = () => setStatus("idle");
    } else if (audioRef.current.src !== url) {
      audioRef.current.src = url;
    }
    audioRef.current.playbackRate = speed;
    await audioRef.current.play();
    setStatus("playing");
  }

  function pause() {
    audioRef.current?.pause();
    setStatus("paused");
  }

  function stop() {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    setStatus("idle");
  }

  return (
    <div className="tts-mini-player">
      <span className="muted">Read aloud: {label}</span>
      <div className="actions">
        <button type="button" disabled={status === "loading"} onClick={() => play()}>
          {status === "loading" ? "Loading…" : "Play"}
        </button>
        <button type="button" onClick={pause} disabled={status !== "playing"}>
          Pause
        </button>
        <button type="button" onClick={stop}>
          Stop
        </button>
        <label>
          Speed{" "}
          <select
            value={speed}
            onChange={(e) => {
              const v = Number(e.target.value);
              setSpeed(v);
              if (audioRef.current) audioRef.current.playbackRate = v;
            }}
          >
            {[0.75, 1, 1.25, 1.5].map((s) => (
              <option key={s} value={s}>
                {s}x
              </option>
            ))}
          </select>
        </label>
      </div>
      {status === "playing" && audioRef.current && (
        <progress max={audioRef.current.duration || 1} value={audioRef.current.currentTime} />
      )}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
