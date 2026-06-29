import { test, expect } from "@playwright/test";
import { apiLogin, ensureAdmin, uiLogin } from "./auth-helpers";

const API = process.env.PLAYWRIGHT_API_BASE || "http://localhost:8000";
const WEB = process.env.PLAYWRIGHT_WEB_BASE || "http://localhost:3000";

test.describe("R2.5 manual workflow", () => {
  test.beforeAll(async ({ request }) => {
    await ensureAdmin(request);
  });

  test("login → jobs list loads", async ({ page }) => {
    await uiLogin(page);
    await page.goto(`${WEB}/jobs`);
    await expect(page.getByRole("heading", { name: /Fresh Jobs|Jobs/i })).toBeVisible();
  });

  test("login → applications page loads", async ({ page }) => {
    await uiLogin(page);
    await page.goto(`${WEB}/applications`);
    await expect(page.getByRole("heading", { name: /Applications/i })).toBeVisible();
  });

  test("autonomous submission rejected via API", async ({ request }) => {
    await apiLogin(request);
    const res = await request.post(`${API}/api/applications/submit`, {
      data: { mode: "AUTONOMOUS", application_id: 1 },
    });
    expect(res.status()).toBe(403);
  });

  test("exact duplicate blocks packet generation via API", async ({ request }) => {
    await apiLogin(request);
    const url = `https://example.com/e2e/dup-${Date.now()}`;
    const first = await request.post(`${API}/api/jobs/ingest`, {
      data: {
        source: "approved_remote_feeds",
        external_id: `e2e-a-${Date.now()}`,
        title: "E2E QE Director",
        company: "E2E Dup Co",
        location: "Remote",
        url,
        description_text: "E2E duplicate test",
      },
    });
    expect(first.ok()).toBeTruthy();
    const job1 = (await first.json()).id;
    const gen1 = await request.post(`${API}/api/applications/jobs/${job1}/generate`);
    expect(gen1.ok()).toBeTruthy();

    const second = await request.post(`${API}/api/jobs/ingest`, {
      data: {
        source: "approved_remote_feeds",
        external_id: `e2e-b-${Date.now()}`,
        title: "E2E QE Director B",
        company: "E2E Dup Co Other",
        location: "Remote",
        url,
        description_text: "E2E duplicate test B",
      },
    });
    const job2 = (await second.json()).id;
    const risk = await request.get(`${API}/api/companies/jobs/${job2}/duplicate-risk`);
    expect((await risk.json()).level).toBe("RED");
    const gen2 = await request.post(`${API}/api/applications/jobs/${job2}/generate`);
    expect(gen2.status()).toBe(409);
  });

  test("vendor representation warning via API", async ({ request }) => {
    await apiLogin(request);
    const suffix = Date.now();
    const clientName = `E2E Client ${suffix}`;
    await request.post(`${API}/api/representations`, {
      data: {
        vendor_name: "E2E Staffing",
        client_name: clientName,
        requisition_id: `REQ-E2E-${suffix}`,
        status: "active",
      },
    });
    const jobRes = await request.post(`${API}/api/jobs/ingest`, {
      data: {
        source: "approved_remote_feeds",
        external_id: `e2e-rep-${suffix}`,
        title: "Director QE",
        company: clientName,
        location: "Remote",
        url: `https://example.com/e2e/rep-${suffix}`,
        description_text: "Representation test",
        requisition_id: `REQ-E2E-${suffix}`,
      },
    });
    const jobId = (await jobRes.json()).id;
    const risk = await request.get(`${API}/api/representations/jobs/${jobId}/representation-risk`);
    expect((await risk.json()).level).toBe("RED");
  });

  test("apply readiness returns official URL and no-auto-submit message", async ({ request }) => {
    await apiLogin(request);
    const fixture = await request.post(`${API}/api/jobs/ingest/fixture`);
    const job = (await fixture.json())[0];
    const ready = await request.get(`${API}/api/applications/jobs/${job.id}/apply-readiness`);
    const body = await ready.json();
    expect(body.official_url).toBeTruthy();
    expect(body.message).toMatch(/not submitted/i);
  });
});
