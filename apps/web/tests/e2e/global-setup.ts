import { execSync } from "node:child_process";
import path from "node:path";

export default async function globalSetup() {
  const root = path.resolve(__dirname, "../../../..");
  const script = path.join(root, "scripts/local/Ensure-E2ETestUser.ps1");
  if (!process.env.E2E_TEST_PASSWORD) {
    console.warn("E2E_TEST_PASSWORD not set — skipping Ensure-E2ETestUser.");
    return;
  }
  try {
    execSync(`pwsh -NoProfile -File "${script}"`, {
      stdio: "inherit",
      cwd: root,
      env: process.env,
    });
  } catch {
    console.warn("Ensure-E2ETestUser skipped (API may not be running — tests may fail login).");
  }
}
