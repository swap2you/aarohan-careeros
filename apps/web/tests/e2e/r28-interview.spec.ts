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

test.describe("R2.8 Interview intelligence", () => {
  test.beforeAll(async ({ request }) => {
    await ensureAdmin(request);
  });

  test("generate interview pack for first job", async ({ page, request }) => {
    await ensureAdmin(request);
    const login = await request.post(`${API}/api/auth/login`, {
      data: { email: "e2e@test.local", password: "E2eTestPass123!", remember_me: true },
    });
    const token = (await login.json()).access_token;
    await request.post(`${API}/api/workflows/ingest/fixture`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    await uiLogin(page);
    await page.goto(`${WEB}/interviews`);
    await page.getByRole("button", { name: /Generate pack/ }).first().click();
    await expect(page.getByText(/STAR stories|interview rounds|gaps/i).first()).toBeVisible({ timeout: 15000 });
  });
});
