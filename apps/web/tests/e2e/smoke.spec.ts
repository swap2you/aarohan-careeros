import { test, expect } from "@playwright/test";

test("dashboard login shell renders", async ({ page }) => {
  await page.goto("http://localhost:3000");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});
