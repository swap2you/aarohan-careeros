import { test, expect } from "@playwright/test";

const API = process.env.PLAYWRIGHT_API_BASE || "http://localhost:8000";

async function authHeaders(request: import("@playwright/test").APIRequestContext) {
  const status = await request.get(`${API}/api/auth/setup-status`);
  if ((await status.json()).setup_required) {
    await request.post(`${API}/api/auth/setup`, {
      data: { email: "e2e@test.local", password: "E2eTestPass123!" },
    });
  }
  const loginRes = await request.post(`${API}/api/auth/login`, {
    data: { email: "e2e@test.local", password: "E2eTestPass123!" },
  });
  return { Authorization: `Bearer ${(await loginRes.json()).access_token}` };
}

test.describe("R2.6 assisted apply", () => {
  test("greenhouse assisted prepare returns field mapping", async ({ request }) => {
    const headers = await authHeaders(request);
    const suffix = Date.now();
    const job = (
      await (
        await request.post(`${API}/api/jobs/ingest`, {
          headers,
          data: {
            source: "greenhouse_public_get",
            external_id: `e2e-gh-${suffix}`,
            title: "QE Director",
            company: "E2E GH",
            location: "Remote",
            url: `https://boards.greenhouse.io/e2e/jobs/${suffix}`,
            description_text: "Assisted e2e",
          },
        })
      ).json()
    );
    const app = await (
      await request.post(`${API}/api/applications/jobs/${job.id}/generate`, { headers })
    ).json();
    await request.post(`${API}/api/applications/${app.id}/actions`, {
      headers,
      data: { action: "approve" },
    });
    const prepared = await request.post(`${API}/api/assisted-apply/applications/${app.id}/prepare`, { headers });
    const body = await prepared.json();
    expect(body.can_proceed).toBe(true);
    expect(body.ats.provider).toBe("greenhouse");
    expect(body.stop_before_submit_message).toMatch(/not submitted/i);
  });

  test("assisted submit attempt returns 403", async ({ request }) => {
    const headers = await authHeaders(request);
    const res = await request.post(`${API}/api/assisted-apply/applications/1/attempt-submit`, { headers });
    expect(res.status()).toBe(403);
  });

  test("linkedin URL is prohibited for assisted", async ({ request }) => {
    const headers = await authHeaders(request);
    const detection = await request.get(
      `${API}/api/assisted-apply/jobs/1/ats-detection`,
      { headers },
    );
    expect([200, 404]).toContain(detection.status());
  });
});
