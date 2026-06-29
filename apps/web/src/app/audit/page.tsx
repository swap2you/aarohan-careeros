"use client";

import { useEffect, useState } from "react";
import { authFetch } from "@/lib/api";

export default function AuditPage() {
  const [logs, setLogs] = useState<Array<{ id: number; event_type: string; created_at: string }>>([]);

  useEffect(() => {
    authFetch(`/api/audit`)
      .then((res) => res.json())
      .then(setLogs);
  }, []);

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
