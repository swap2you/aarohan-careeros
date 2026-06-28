"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

export default function ApplicationsPage() {
  const [items, setItems] = useState<Array<{ id: number; state: string; job_id: number }>>([]);

  useEffect(() => {
    const token = localStorage.getItem("careeros_token");
    if (!token) return;
    fetch(`${API_BASE}/api/applications`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => res.json())
      .then(setItems);
  }, []);

  return (
    <div>
      <h1>Applications</h1>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Job</th>
              <th>State</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td>{item.id}</td>
                <td>{item.job_id}</td>
                <td>{item.state}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
