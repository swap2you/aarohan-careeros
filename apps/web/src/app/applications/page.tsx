"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

type Application = {
  id: number;
  state: string;
  job_id: number;
  packet_metadata?: {
    document_quality?: { passed?: boolean; template_version?: string };
  };
};

type QualityReport = {
  passed: boolean;
  template_version?: string;
  ats_diagnostics?: { issues?: string[]; warnings?: string[] };
  answer_sheet?: string;
};

export default function ApplicationsPage() {
  const [items, setItems] = useState<Application[]>([]);
  const [selectedQuality, setSelectedQuality] = useState<QualityReport | null>(null);

  function token() {
    return localStorage.getItem("careeros_token") || "";
  }

  useEffect(() => {
    fetch(`${API_BASE}/api/applications`, { headers: { Authorization: `Bearer ${token()}` } })
      .then((res) => res.json())
      .then(setItems);
  }, []);

  async function loadQuality(applicationId: number) {
    const response = await fetch(`${API_BASE}/api/documents/applications/${applicationId}/quality`, {
      headers: { Authorization: `Bearer ${token()}` },
    });
    setSelectedQuality(await response.json());
  }

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
              <th>Doc quality</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td>{item.id}</td>
                <td>{item.job_id}</td>
                <td>{item.state}</td>
                <td>
                  {item.packet_metadata?.document_quality?.passed === false
                    ? "FAIL"
                    : item.packet_metadata?.document_quality?.passed
                      ? "PASS"
                      : "—"}
                </td>
                <td>
                  <button type="button" onClick={() => loadQuality(item.id)}>
                    Quality report
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {selectedQuality && (
        <div className={`card ${selectedQuality.passed ? "risk-green" : "risk-red"}`}>
          <h3>Document quality {selectedQuality.passed ? "PASS" : "FAIL"}</h3>
          <p>Template: {selectedQuality.template_version}</p>
          {selectedQuality.ats_diagnostics?.warnings?.map((w) => (
            <p key={w}>{w}</p>
          ))}
          {selectedQuality.answer_sheet && <pre>{selectedQuality.answer_sheet}</pre>}
        </div>
      )}
    </div>
  );
}
