"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";

type Job = {
  id: number;
  title: string;
  company: string;
  state: string;
  score?: { total_score: number };
};

export default function ShortlistPage() {
  const { apiFetch, status: authStatus } = useAuth();
  const [jobs, setJobs] = useState<Job[]>([]);

  useEffect(() => {
    if (authStatus !== "authenticated") return;
    apiFetch("/api/jobs")
      .then((res) => (res.ok ? res.json() : []))
      .then((rows: Job[]) =>
        setJobs(rows.filter((j) => j.state === "SHORTLISTED" || (j.score?.total_score ?? 0) >= 75)),
      );
  }, [apiFetch, authStatus]);

  return (
    <div>
      <h1>Shortlist</h1>
      <p>Jobs shortlisted for packet generation (score ≥ 75 or SHORTLISTED state).</p>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Company</th>
              <th>Title</th>
              <th>State</th>
              <th>Score</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id}>
                <td>{job.company}</td>
                <td>
                  <a href={`/jobs/${job.id}`}>{job.title}</a>
                </td>
                <td>{job.state}</td>
                <td>{job.score?.total_score ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
