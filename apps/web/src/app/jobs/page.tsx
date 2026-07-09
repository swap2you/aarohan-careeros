"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useDeploymentEnvironment } from "@/components/EnvironmentBadge";
import { API_BASE, authFetch } from "@/lib/api";

type JobScore = {
  total_score: number;
  trust_score?: number;
  hard_filter_passed?: boolean;
  recommendation?: string;
  match_card?: { headline?: string; trust_highlights?: string[]; fit_highlights?: string[] };
};

type Job = {
  id: number;
  title: string;
  company: string;
  state: string;
  source?: string;
  location?: string | null;
  workplace_type?: string | null;
  salary_min?: number | null;
  salary_max?: number | null;
  role_family?: string | null;
  is_expired?: boolean;
  source_verified?: boolean;
  match_summary?: string | null;
  selected?: boolean;
  score?: JobScore;
};

type WorkflowResult = { action: string; success: number; failed: number; details: unknown[] };

const PAGE_SIZES = [10, 25, 50, 100];

type ColumnSortField = "salary" | "fit";
type ColumnSort = { field: ColumnSortField; dir: "asc" | "desc" } | null;

function sortIndicator(active: ColumnSort, field: ColumnSortField) {
  if (active?.field !== field) return "↕";
  return active.dir === "asc" ? "↑" : "↓";
}

function formatSalary(job: Job) {
  if (!job.salary_min && !job.salary_max) return "Not disclosed";
  if (job.salary_min && job.salary_max && job.salary_min !== job.salary_max) {
    return `$${job.salary_min.toLocaleString()} – $${job.salary_max.toLocaleString()}`;
  }
  const value = job.salary_max || job.salary_min;
  return value ? `$${value.toLocaleString()}` : "Not disclosed";
}

function truncateTitle(title: string, max = 72) {
  const t = title.trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max - 1)}…`;
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [pageCount, setPageCount] = useState(1);
  const [search, setSearch] = useState("");
  const [source, setSource] = useState("");
  const [company, setCompany] = useState("");
  const [roleFamily, setRoleFamily] = useState("");
  const [workplaceType, setWorkplaceType] = useState("");
  const [filterSort, setFilterSort] = useState("newest");
  const [columnSort, setColumnSort] = useState<ColumnSort>(null);
  const [status, setStatus] = useState<string>("");
  const [forwardUrl, setForwardUrl] = useState("");
  const [profile, setProfile] = useState("tpm_delivery");
  const { showFixtureControls } = useDeploymentEnvironment();

  const load = useCallback(async () => {
    const apiSortBy = columnSort?.field ?? filterSort;
    const apiSortDir = columnSort?.dir ?? "desc";
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
      sort_by: apiSortBy,
      sort_dir: apiSortDir,
    });
    if (search) params.set("search", search);
    if (source) params.set("source", source);
    if (company) params.set("company", company);
    if (roleFamily) params.set("role_family", roleFamily);
    if (workplaceType) params.set("workplace_type", workplaceType);
    const response = await authFetch(`/api/jobs?${params.toString()}`);
    const data = await response.json();
    setJobs(data.items || data);
    setTotal(data.total ?? (data.items || data).length);
    setPageCount(data.page_count || 1);
  }, [page, pageSize, search, source, company, roleFamily, workplaceType, filterSort, columnSort]);

  useEffect(() => {
    load();
  }, [load]);

  function cycleColumnSort(field: ColumnSortField) {
    setPage(1);
    setColumnSort((current) => {
      if (current?.field !== field) return { field, dir: "asc" };
      if (current.dir === "asc") return { field, dir: "desc" };
      return null;
    });
  }

  function onFilterSortChange(value: string) {
    setFilterSort(value);
    setColumnSort(null);
    setPage(1);
  }

  async function runWorkflow(path: string, body?: unknown) {
    setStatus("Running...");
    const response = await authFetch(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    });
    const data: WorkflowResult = await response.json();
    setStatus(`${data.action}: success=${data.success}, failed=${data.failed}`);
    await load();
  }

  function toggleSelect(id: number) {
    setJobs((current) =>
      current.map((job) => (job.id === id ? { ...job, selected: !job.selected } : job)),
    );
  }

  async function generateSelected() {
    const ids = jobs.filter((j) => j.selected).map((j) => j.id);
    if (!ids.length) {
      setStatus("Select at least one job.");
      return;
    }
    await runWorkflow("/api/workflows/generate-packets", { job_ids: ids, resume_profile: profile });
  }

  return (
    <div>
      <h1>Fresh Jobs & Manual Workflows</h1>
      <div className="card actions">
        {showFixtureControls && (
          <button onClick={() => runWorkflow("/api/workflows/ingest/fixture")}>Import Fixture</button>
        )}
        <button onClick={() => runWorkflow("/api/workflows/ingest/public")}>Ingest Public Feed</button>
        <button onClick={() => runWorkflow("/api/workflows/score-all")}>Score All New Jobs</button>
        <button onClick={generateSelected}>Generate Selected Packets</button>
        <Link href="/opportunities/new" className="inline-link">
          New Opportunity
        </Link>
      </div>
      <div className="card">
        <div className="filters-grid">
          <input placeholder="Title / keyword" value={search} onChange={(e) => setSearch(e.target.value)} />
          <input placeholder="Source (linkedin, indeed…)" value={source} onChange={(e) => setSource(e.target.value)} />
          <input placeholder="Company" value={company} onChange={(e) => setCompany(e.target.value)} />
          <input placeholder="Role family" value={roleFamily} onChange={(e) => setRoleFamily(e.target.value)} />
          <select value={workplaceType} onChange={(e) => setWorkplaceType(e.target.value)}>
            <option value="">Any work mode</option>
            <option value="remote">Remote</option>
            <option value="hybrid">Hybrid</option>
            <option value="fully_remote_us">Fully remote (US)</option>
          </select>
          <select value={filterSort} onChange={(e) => onFilterSortChange(e.target.value)}>
            <option value="newest">Newest</option>
            <option value="trust">Highest trust</option>
            <option value="company">Company</option>
            <option value="title">Title</option>
          </select>
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setPage(1);
            }}
          >
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size} / page
              </option>
            ))}
          </select>
          <button type="button" onClick={() => load()}>
            Apply filters
          </button>
        </div>
        <label>Resume profile </label>
        <select value={profile} onChange={(e) => setProfile(e.target.value)}>
          <option value="tpm_delivery">TPM / Program Manager</option>
          <option value="qe_manager">QE Manager</option>
          <option value="director_qe">Director-targeted QE</option>
          <option value="platform_architect">Principal / Architect</option>
          <option value="qe_leadership">QE Leadership</option>
          <option value="ai_enabled_qe">AI-Enabled QE</option>
        </select>
        <div style={{ marginTop: "1rem" }}>
          <input placeholder="Forwarded job URL" value={forwardUrl} onChange={(e) => setForwardUrl(e.target.value)} />
          <button onClick={() => runWorkflow("/api/workflows/import-url", { url: forwardUrl })}>Import URL</button>
        </div>
        {status && <p className="status">{status}</p>}
      </div>
      <div className="card table-card">
        <p>{total} jobs (fixture/test data hidden in owner mode)</p>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th className="col-check"></th>
                <th className="col-job">Job</th>
                <th>Source</th>
                <th>
                  <button
                    type="button"
                    className={`th-sort${columnSort?.field === "salary" ? " active" : ""}`}
                    onClick={() => cycleColumnSort("salary")}
                    aria-sort={
                      columnSort?.field === "salary"
                        ? columnSort.dir === "asc"
                          ? "ascending"
                          : "descending"
                        : "none"
                    }
                  >
                    Salary
                    <span className="th-sort-indicator" aria-hidden="true">
                      {sortIndicator(columnSort, "salary")}
                    </span>
                  </button>
                </th>
                <th>Family</th>
                <th>
                  <button
                    type="button"
                    className={`th-sort${columnSort?.field === "fit" ? " active" : ""}`}
                    onClick={() => cycleColumnSort("fit")}
                    aria-sort={
                      columnSort?.field === "fit"
                        ? columnSort.dir === "asc"
                          ? "ascending"
                          : "descending"
                        : "none"
                    }
                  >
                    Fit
                    <span className="th-sort-indicator" aria-hidden="true">
                      {sortIndicator(columnSort, "fit")}
                    </span>
                  </button>
                </th>
                <th>Trust</th>
                <th>Filter</th>
                <th>State</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id}>
                  <td>
                    <input type="checkbox" checked={!!job.selected} onChange={() => toggleSelect(job.id)} />
                  </td>
                  <td className="job-cell">
                    <Link href={`/jobs/${job.id}`} className="job-title-link">
                      {truncateTitle(job.title)}
                    </Link>
                    <div className="job-meta">
                      {job.company}
                      {job.location ? ` · ${job.location}` : ""}
                      {job.is_expired ? " · expired" : ""}
                    </div>
                    {job.match_summary && <p className="job-summary">{job.match_summary}</p>}
                  </td>
                <td>{job.source || "—"}</td>
                <td>{formatSalary(job)}</td>
                <td>{job.role_family ?? "—"}</td>
                <td>{job.score?.total_score ?? "—"}</td>
                <td>{job.score?.trust_score ?? "—"}</td>
                <td>{job.score?.hard_filter_passed === false ? "FAIL" : job.score ? "PASS" : "—"}</td>
                <td>{job.state}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
        <div className="pagination">
          <span>
            Page {page} of {pageCount}
          </span>
          <button type="button" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
            Previous
          </button>
          <button type="button" disabled={page >= pageCount} onClick={() => setPage((p) => p + 1)}>
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
