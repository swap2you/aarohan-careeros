import { test, expect } from "@playwright/test";

const API = process.env.PLAYWRIGHT_API_BASE || "http://localhost:8000";
const WEB = process.env.PLAYWRIGHT_WEB_BASE || "http://localhost:3000";

async function ensureAdmin(request: import("@playwright/test").APIRequestContext) {
  const status = await request.get(`${API}/api/auth/setup-status`);
  const body = await status.json();
  if (body.setup_required) {
    await request.post(`${API}/api/auth/setup`, {
      data: { email: "e2e@test.local", password: "E2eTestPass123!" },
    });
  }
}

async function authHeaders(request: import("@playwright/test").APIRequestContext) {
  await ensureAdmin(request);
  const loginRes = await request.post(`${API}/api/auth/login`, {
    data: { email: "e2e@test.local", password: "E2eTestPass123!" },
  });
  const token = (await loginRes.json()).access_token;
  return { Authorization: `Bearer ${token}` };
}

async function login(page: import("@playwright/test").Page) {
  await page.goto(WEB);
  const setupHeading = page.getByRole("heading", { name: /First-run administrator setup/ });
  if (await setupHeading.isVisible().catch(() => false)) {
    await page.getByLabel(/email/i).fill("e2e@test.local");
    await page.getByLabel(/password/i).fill("E2eTestPass123!");
    await page.getByRole("button", { name: /Create administrator|Sign in/i }).click();
  } else {
    await page.getByLabel(/email/i).fill("e2e@test.local");
    await page.getByLabel(/password/i).fill("E2eTestPass123!");
    await page.getByRole("button", { name: /Sign in/i }).click();
  }
  await expect(page.getByRole("navigation")).toBeVisible({ timeout: 15000 });
}

test.describe("R2.5 manual workflow", () => {
  test.beforeAll(async ({ request }) => {
    await ensureAdmin(request);
  });

  test("login → jobs list loads", async ({ page }) => {
    await login(page);
    await page.goto(`${WEB}/jobs`);
    await expect(page.getByRole("heading", { name: /Jobs/i })).toBeVisible();
  });

  test("login → applications page loads", async ({ page }) => {
    await login(page);
    await page.goto(`${WEB}/applications`);
    await expect(page.getByRole("heading", { name: /Applications/i })).toBeVisible();
  });

  test("autonomous submission rejected via API", async ({ request }) => {
    const headers = await authHeaders(request);
    const res = await request.post(`${API}/api/applications/submit`, {
      headers,
      data: { mode: "AUTONOMOUS", application_id: 1 },
    });
    expect(res.status()).toBe(403);
  });

  test("exact duplicate blocks packet generation via API", async ({ request }) => {
    const headers = await authHeaders(request);
    const url = `https://example.com/e2e/dup-${Date.now()}`;
    const first = await request.post(`${API}/api/jobs/ingest`, {
      headers,
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
    const gen1 = await request.post(`${API}/api/applications/jobs/${job1}/generate`, { headers });
    expect(gen1.ok()).toBeTruthy();

    const second = await request.post(`${API}/api/jobs/ingest`, {
      headers,
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
    const risk = await request.get(`${API}/api/companies/jobs/${job2}/duplicate-risk`, { headers });
    expect((await risk.json()).level).toBe("RED");
    const gen2 = await request.post(`${API}/api/applications/jobs/${job2}/generate`, { headers });
    expect(gen2.status()).toBe(409);
  });

  test("vendor representation warning via API", async ({ request }) => {
    const headers = await authHeaders(request);
    const suffix = Date.now();
    const clientName = `E2E Client ${suffix}`;
    await request.post(`${API}/api/representations`, {
      headers,
      data: {
        vendor_name: "E2E Staffing",
        client_name: clientName,
        requisition_id: `REQ-E2E-${suffix}`,
        status: "active",
      },
    });
    const jobRes = await request.post(`${API}/api/jobs/ingest`, {
      headers,
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
    const risk = await request.get(`${API}/api/representations/jobs/${jobId}/representation-risk`, {
      headers,
    });
    expect((await risk.json()).level).toBe("RED");
  });

  test("apply readiness returns official URL and no-auto-submit message", async ({ request }) => {
    const headers = await authHeaders(request);
    const fixture = await request.post(`${API}/api/jobs/ingest/fixture`, { headers });
    const job = (await fixture.json())[0];
    const ready = await request.get(`${API}/api/applications/jobs/${job.id}/apply-readiness`, { headers });
    const body = await ready.json();
    expect(body.official_url).toBeTruthy();
    expect(body.message).toMatch(/not submitted/i);
  });
});
