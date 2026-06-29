import { execSync } from "node:child_process";
import path from "node:path";

export default async function globalSetup() {
  const root = path.resolve(__dirname, "../../../..");
  const script = path.join(root, "scripts/local/Ensure-E2ETestUser.ps1");
  try {
    execSync(`pwsh -NoProfile -File "${script}"`, { stdio: "inherit", cwd: root });
  } catch {
    console.warn("Ensure-E2ETestUser skipped (API may not be running — tests may fail login).");
  }
}
