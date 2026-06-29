import { test, expect, type APIRequestContext, type Page } from "@playwright/test";

const API = process.env.PLAYWRIGHT_API_BASE || "http://localhost:8000";
const WEB = process.env.PLAYWRIGHT_WEB_BASE || "http://localhost:3000";
const E2E_EMAIL = "e2e@test.local";
const E2E_PASSWORD = "E2eTestPass123!";

export async function ensureAdmin(request: APIRequestContext) {
  const status = await request.get(`${API}/api/auth/setup-status`);
  const body = await status.json();
  if (body.setup_required) {
    await request.post(`${API}/api/auth/setup`, {
      data: { email: E2E_EMAIL, password: E2E_PASSWORD, remember_me: true },
    });
  }
}

export async function apiLogin(request: APIRequestContext) {
  await ensureAdmin(request);
  const loginRes = await request.post(`${API}/api/auth/login`, {
    data: { email: E2E_EMAIL, password: E2E_PASSWORD, remember_me: true },
  });
  expect(loginRes.ok()).toBeTruthy();
  const body = await loginRes.json();
  expect(body.authenticated).toBe(true);
}

export async function uiLogin(page: Page) {
  await page.goto(`${WEB}/login`);
  await expect(
    page.getByRole("heading", { name: /Sign in|First-run administrator setup/ }),
  ).toBeVisible({ timeout: 20000 });
  await page.getByLabel("Email").fill(E2E_EMAIL);
  await page.locator('input[type="password"]').fill(E2E_PASSWORD);
  const isSetup = await page.getByRole("heading", { name: /First-run administrator setup/ }).isVisible();
  await page.getByRole("button", { name: isSetup ? /Create administrator/ : /Sign in/ }).click();
  await expect(page.getByRole("heading", { name: /Executive Overview/ })).toBeVisible({ timeout: 20000 });
}
