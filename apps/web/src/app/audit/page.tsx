"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";

export default function AuditPage() {
  const { apiFetch, status: authStatus } = useAuth();
  const [logs, setLogs] = useState<Array<{ id: number; event_type: string; created_at: string }>>([]);

  useEffect(() => {
    if (authStatus !== "authenticated") return;
    apiFetch("/api/audit")
      .then((res) => (res.ok ? res.json() : []))
      .then(setLogs);
  }, [apiFetch, authStatus]);

  return (
    <div>
      <h1>Audit Log</h1>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Event</th>
              <th>Timestamp</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id}>
                <td>{log.event_type}</td>
                <td>{log.created_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
