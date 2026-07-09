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
  await page.goto(WEB);
  await expect(
    page.getByRole("heading", { name: /Sign in to Aarohan CareerOS|First-run administrator setup/ }),
  ).toBeVisible({ timeout: 20000 });
  await page.getByLabel("Email").fill("e2e@test.local");
  await page.locator('input[type="password"]').fill("E2eTestPass123!");
  const isSetup = await page
    .getByRole("heading", { name: /First-run administrator setup/ })
    .isVisible();
  await page.getByRole("button", { name: isSetup ? /Create administrator/ : /Sign in/ }).click();
  await expect(page.getByRole("heading", { name: /Executive Overview/ })).toBeVisible({ timeout: 20000 });
}

test.describe("R2.6.1 auth session lifecycle", () => {
  test.beforeAll(async ({ request }) => {
    await ensureAdmin(request);
  });

  test("unauthenticated visit shows login", async ({ page }) => {
    await page.context().clearCookies();
    await page.goto(WEB);
    await expect(page.getByRole("heading", { name: /Sign in to Aarohan CareerOS/ })).toBeVisible();
  });

  test("login with remember me loads overview with metrics", async ({ page }) => {
    await uiLogin(page);
    await expect(page.getByText("Total Jobs")).toBeVisible();
  });

  test("protected routes require session", async ({ page }) => {
    await uiLogin(page);
    for (const path of ["/jobs", "/applications", "/settings", "/companies", "/audit"]) {
      await page.goto(`${WEB}${path}`);
      await expect(page.locator("nav.nav")).toBeVisible();
    }
  });

  test("logout returns to login and blocks protected routes", async ({ page }) => {
    await uiLogin(page);
    await page.getByRole("button", { name: /Sign out|Logout/i }).click();
    await expect(page.getByRole("heading", { name: /Sign in to Aarohan CareerOS/ })).toBeVisible({
      timeout: 15000,
    });
    await page.goto(`${WEB}/jobs`);
    await expect(page.getByRole("heading", { name: /Sign in to Aarohan CareerOS/ })).toBeVisible();
  });

  test("tampered session shows session expired message", async ({ page, context }) => {
    await context.addCookies([
      {
        name: "careeros_session",
        value: "tampered-session-token",
        domain: "localhost",
        path: "/",
      },
    ]);
    await page.goto(WEB);
    await expect(page.getByText(/Your session expired/i)).toBeVisible({ timeout: 15000 });
  });

  test("no nav shell before auth on direct protected route", async ({ page }) => {
    await page.context().clearCookies();
    await page.goto(`${WEB}/jobs`);
    await expect(page.locator("nav.nav")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: /Sign in to Aarohan CareerOS/ })).toBeVisible();
  });

  test("password visibility toggle on login screen", async ({ page }) => {
    await page.context().clearCookies();
    await page.goto(`${WEB}/login`);
    await expect(
      page.getByRole("heading", { name: /Sign in to Aarohan CareerOS|First-run administrator setup/ }),
    ).toBeVisible({ timeout: 20000 });

    const password = page.locator("#careeros-password");
    await expect(password).toHaveAttribute("type", "password");
    await password.fill("E2eTestPass123!");

    const showButton = page.getByRole("button", { name: "Show password" });
    await showButton.click();
    await expect(password).toHaveAttribute("type", "text");
    await expect(page.getByRole("button", { name: "Hide password" })).toBeVisible();

    const hideButton = page.getByRole("button", { name: "Hide password" });
    await hideButton.focus();
    await page.keyboard.press("Enter");
    await expect(password).toHaveAttribute("type", "password");
    await expect(page.getByRole("button", { name: "Show password" })).toBeVisible();
  });

  test("Enter Local Admin hidden when bypass disabled", async ({ page }) => {
    await page.context().clearCookies();
    await page.goto(`${WEB}/login`);
    await expect(page.getByRole("button", { name: "Enter Local Admin" })).toHaveCount(0);
  });
});
