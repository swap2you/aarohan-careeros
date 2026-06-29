"use client";

import { useEffect, useState } from "react";
import { API_BASE, authFetch } from "@/lib/api";

type Signal = {
  id: number;
  signal_type: string;
  sender: string | null;
  subject: string | null;
  job_id: number | null;
  received_at: string;
};

export default function RecruiterSignalsPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [message, setMessage] = useState("");


  async function load() {
    const response = await authFetch(`/api/recruiter-signals`);
    setSignals(await response.json());
  }

  useEffect(() => {
    load();
  }, []);

  async function syncGmail() {
    const response = await authFetch(`/api/integrations/gmail/sync`, {
      method: "POST", });
    const data = await response.json();
    setMessage(`Synced ${data.processed ?? 0} messages`);
    await load();
  }

  return (
    <div>
      <h1>Recruiter Signals</h1>
      <div className="actions">
        <button onClick={syncGmail}>Sync Gmail (read-only)</button>
      </div>
      {message && <p className="status">{message}</p>}
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Type</th>
              <th>Sender</th>
              <th>Subject</th>
              <th>Received</th>
            </tr>
          </thead>
          <tbody>
            {signals.map((s) => (
              <tr key={s.id}>
                <td>{s.signal_type}</td>
                <td>{s.sender}</td>
                <td>{s.subject}</td>
                <td>{new Date(s.received_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
