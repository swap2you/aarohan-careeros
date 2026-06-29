import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  globalSetup: "./tests/e2e/global-setup.ts",
  timeout: 30000,
  outputDir: "../../artifacts/playwright/test-results",
  use: {
    baseURL: "http://localhost:3000",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  reporter: [["list"], ["html", { outputFolder: "../../artifacts/playwright/report", open: "never" }]],
});
