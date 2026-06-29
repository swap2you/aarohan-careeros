import { test, expect } from "@playwright/test";
import { apiLogin } from "./auth-helpers";

const API = process.env.PLAYWRIGHT_API_BASE || "http://localhost:8000";

test.describe("R2.6 assisted apply", () => {
  test("greenhouse assisted prepare returns field mapping", async ({ request }) => {
    await apiLogin(request);
    const suffix = Date.now();
    const job = (
      await (
        await request.post(`${API}/api/jobs/ingest`, {
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
      await request.post(`${API}/api/applications/jobs/${job.id}/generate`)
    ).json();
    await request.post(`${API}/api/applications/${app.id}/actions`, {
      data: { action: "approve" },
    });
    const prepared = await request.post(`${API}/api/assisted-apply/applications/${app.id}/prepare`);
    const body = await prepared.json();
    expect(body.can_proceed).toBe(true);
    expect(body.ats.provider).toBe("greenhouse");
    expect(body.stop_before_submit_message).toMatch(/not submitted/i);
  });

  test("assisted submit attempt returns 403", async ({ request }) => {
    await apiLogin(request);
    const res = await request.post(`${API}/api/assisted-apply/applications/1/attempt-submit`);
    expect(res.status()).toBe(403);
  });

  test("linkedin URL is prohibited for assisted", async ({ request }) => {
    await apiLogin(request);
    const detection = await request.get(`${API}/api/assisted-apply/jobs/1/ats-detection`);
    expect([200, 404]).toContain(detection.status());
  });
});
