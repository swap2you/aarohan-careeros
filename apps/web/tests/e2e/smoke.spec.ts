import { test, expect } from "@playwright/test";

const WEB = process.env.PLAYWRIGHT_WEB_BASE || "http://localhost:3000";

test("dashboard login shell renders", async ({ page, context }) => {
  await context.clearCookies();
  await page.goto(WEB);
  await expect(
    page.getByRole("heading", { name: /Sign in to Aarohan CareerOS|First-run administrator setup/ }),
  ).toBeVisible({ timeout: 15000 });
});
