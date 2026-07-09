"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { authFetch } from "@/lib/api";

type Job = {
  id: number;
  title: string;
  company: string;
  state: string;
  score?: { total_score: number };
};

export default function ShortlistPage() {
  const [jobs, setJobs] = useState<Job[]>([]);


  useEffect(() => {
    authFetch(`/api/jobs?page=1&page_size=100`)
      .then((res) => res.json())
      .then((data) => {
        const rows: Job[] = data.items || data;
        setJobs(rows.filter((j) => j.state === "SHORTLISTED" || (j.score?.total_score ?? 0) >= 75));
      });
  }, []);

  return (
    <div>
      <h1>Shortlist</h1>
      <p>Jobs shortlisted for packet generation (score ≥ 75 or SHORTLISTED state).</p>
      <div className="card table-card">
        <div className="table-scroll">
        <table className="data-table">
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
                  <Link href={`/jobs/${job.id}`} className="job-title-link">
                    {job.title}
                  </Link>
                </td>
                <td>{job.state}</td>
                <td>{job.score?.total_score ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>
    </div>
  );
}
