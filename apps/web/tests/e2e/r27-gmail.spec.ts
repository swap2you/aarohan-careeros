import { test, expect } from "@playwright/test";

const API = process.env.PLAYWRIGHT_API_BASE || "http://localhost:8000";
const WEB = process.env.PLAYWRIGHT_WEB_BASE || "http://localhost:3000";

async function ensureAdmin(request: import("@playwright/test").APIRequestContext) {
  const status = await request.get(`${API}/api/auth/setup-status`);
  const body = await status.json();
  if (body.setup_required) {
    await request.post(`${API}/api/auth/setup`, {
      data: { email: "e2e@test.local", password: "E2eTestPass123!", remember_me: true },
    });
  }
}

async function uiLogin(page: import("@playwright/test").Page) {
  await page.goto(`${WEB}/login`);
  await page.getByLabel("Email").fill("e2e@test.local");
  await page.locator('input[type="password"]').fill("E2eTestPass123!");
  const isSetup = await page.getByRole("heading", { name: /First-run administrator setup/ }).isVisible();
  await page.getByRole("button", { name: isSetup ? /Create administrator/ : /Sign in/ }).click();
  await expect(page.getByRole("heading", { name: /Executive Overview/ })).toBeVisible({ timeout: 20000 });
}

test.describe("R2.7 Gmail lifecycle", () => {
  test.beforeAll(async ({ request }) => {
    await ensureAdmin(request);
  });

  test("fixture sync populates lifecycle table", async ({ page }) => {
    await uiLogin(page);
    await page.goto(`${WEB}/recruiter-signals`);
    await page.getByRole("button", { name: /Sync fixtures/ }).click();
    await expect(page.getByText(/Processed \d+ messages/)).toBeVisible({ timeout: 15000 });
    await expect(page.locator("table tbody tr").first()).toBeVisible({ timeout: 10000 });
  });
});
