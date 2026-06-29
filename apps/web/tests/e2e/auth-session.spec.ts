import { test, expect } from "@playwright/test";
import { apiLogin, ensureAdmin, uiLogin } from "./auth-helpers";

const API = process.env.PLAYWRIGHT_API_BASE || "http://localhost:8000";
const WEB = process.env.PLAYWRIGHT_WEB_BASE || "http://localhost:3000";

const PROTECTED_ROUTES = ["/", "/jobs", "/applications", "/settings", "/companies", "/audit"];

test.describe("Auth session lifecycle", () => {
  test.beforeAll(async ({ request }) => {
    await ensureAdmin(request);
  });

  test("unauthenticated user sees login", async ({ page }) => {
    await page.context().clearCookies();
    await page.goto(WEB);
    await expect(page.getByRole("heading", { name: /Sign in|First-run administrator setup/ })).toBeVisible();
  });

  test("login with remember me loads overview with data", async ({ page }) => {
    await uiLogin(page);
    await expect(page.getByText("Total Jobs")).toBeVisible();
    await expect(page.locator(".grid .card").first()).not.toHaveText(/^—$/);
  });

  test("protected routes require login", async ({ page }) => {
    await page.context().clearCookies();
    for (const route of PROTECTED_ROUTES) {
      await page.goto(`${WEB}${route}`);
      await expect(page.getByRole("heading", { name: /Sign in|First-run administrator setup/ })).toBeVisible({
        timeout: 15000,
      });
    }
  });

  test("session survives API re-auth via cookie", async ({ request }) => {
    await apiLogin(request);
    const session = await request.get(`${API}/api/auth/session`);
    expect((await session.json()).authenticated).toBe(true);
    const analytics = await request.get(`${API}/api/analytics`);
    expect(analytics.ok()).toBeTruthy();
  });

  test("logout returns to login and blocks protected routes", async ({ page }) => {
    await uiLogin(page);
    await page.getByRole("button", { name: /Log out/i }).click();
    await expect(page.getByRole("heading", { name: /Sign in/i })).toBeVisible();
    await page.goto(`${WEB}/jobs`);
    await expect(page.getByRole("heading", { name: /Sign in/i })).toBeVisible();
  });

  test("session expired message on login", async ({ page }) => {
    await page.goto(`${WEB}/login?reason=session_expired`);
    await expect(page.getByText(/Your session expired/i)).toBeVisible();
  });

  test("autonomous 403 via API does not clear session", async ({ request }) => {
    await apiLogin(request);
    const res = await request.post(`${API}/api/applications/submit`, {
      data: { mode: "AUTONOMOUS", application_id: 1 },
    });
    expect(res.status()).toBe(403);
    const session = await request.get(`${API}/api/auth/session`);
    expect((await session.json()).authenticated).toBe(true);
  });

  test("invalid session cookie redirects to login", async ({ page, context }) => {
    await context.addCookies([
      {
        name: "careeros_session",
        value: "invalid-session-token-value",
        domain: "localhost",
        path: "/",
        httpOnly: true,
        secure: false,
        sameSite: "Lax",
      },
    ]);
    await page.goto(WEB);
    await expect(page.getByRole("heading", { name: /Sign in/i })).toBeVisible({ timeout: 15000 });
  });
});
