import { test, expect } from "@playwright/test";

const API = process.env.PLAYWRIGHT_API_BASE || "http://localhost:8000";
const WEB = process.env.PLAYWRIGHT_WEB_BASE || "http://localhost:3000";

async function uiLogin(page: import("@playwright/test").Page) {
  await page.goto(`${WEB}/login`);
  await page.getByLabel("Email").fill("e2e@test.local");
  await page.locator('input[type="password"]').fill("E2eTestPass123!");
  await page.getByRole("button", { name: /Sign in|Create administrator/i }).click();
  await expect(page.getByRole("heading", { name: /Executive Overview/ })).toBeVisible({ timeout: 20000 });
}

test.describe("Job detail stability", () => {
  test("valid job detail loads without crash", async ({ page, request }) => {
    await uiLogin(page);
    const login = await request.post(`${API}/api/auth/login`, {
      data: { email: "e2e@test.local", password: "E2eTestPass123!", remember_me: true },
    });
    expect(login.ok()).toBeTruthy();

    const jobRes = await request.post(`${API}/api/jobs/ingest`, {
      data: {
        source: "manual",
        external_id: `e2e-detail-${Date.now()}`,
        title: "E2E Detail Job",
        company: "E2E GH",
        url: "https://boards.greenhouse.io/e2e/jobs/1",
        description_text: "Detailed description for Playwright.",
      },
    });
    expect(jobRes.ok()).toBeTruthy();
    const job = await jobRes.json();

    await page.goto(`${WEB}/jobs/${job.id}`);
    await expect(page.getByRole("heading", { name: "E2E Detail Job" })).toBeVisible();
    await expect(page.getByText("Back to jobs")).toBeVisible();
    await expect(page.getByText("Detailed description")).toBeVisible();
  });

  test("missing job shows error panel not login redirect", async ({ page }) => {
    await uiLogin(page);
    await page.goto(`${WEB}/jobs/999999999`);
    await expect(page.getByRole("heading", { name: /Job detail unavailable|not found/i })).toBeVisible({
      timeout: 10000,
    });
    await expect(page).not.toHaveURL(/\/login/);
  });
});
