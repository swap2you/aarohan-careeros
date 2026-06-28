"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { API_BASE } from "@/lib/api";

type JobDetail = {
  id: number;
  title: string;
  company: string;
  location: string | null;
  state: string;
  description_text: string;
  url: string;
  score?: {
    total_score: number;
    compensation_score: number;
    remote_score: number;
    technical_fit_score: number;
    fit_analysis: string | null;
    gap_analysis: string | null;
  };
};

export default function JobDetailPage() {
  const params = useParams();
  const jobId = params?.id as string;
  const [job, setJob] = useState<JobDetail | null>(null);

  function token() {
    return localStorage.getItem("careeros_token") || "";
  }

  useEffect(() => {
    if (!jobId) return;
    fetch(`${API_BASE}/api/jobs/${jobId}`, { headers: { Authorization: `Bearer ${token()}` } })
      .then((res) => res.json())
      .then(setJob);
  }, [jobId]);

  if (!job) return <p>Loading job detail...</p>;

  return (
    <div>
      <h1>{job.title}</h1>
      <p>
        {job.company} · {job.location ?? "Location TBD"} · {job.state}
      </p>
      <div className="card">
        <h3>Score</h3>
        <p>Total: {job.score?.total_score ?? "—"}</p>
        <pre>{JSON.stringify(job.score, null, 2)}</pre>
      </div>
      <div className="card">
        <h3>Description</h3>
        <pre>{job.description_text}</pre>
      </div>
      <div className="card">
        <a href={job.url} target="_blank" rel="noreferrer">
          View posting
        </a>
      </div>
    </div>
  );
}
