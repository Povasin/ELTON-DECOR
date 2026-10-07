import { defineConfig, devices } from "@playwright/test";

const siteURL = process.env.ELTON_E2E_BASE_URL ?? "http://localhost:3000";
const runtimeEnabled = process.env.ELTON_E2E_ENABLED === "1";

/**
 * Browser checks are intentionally opt-in.  A local build without a running
 * API/PostgreSQL must remain useful, so the specs mark the runtime gate as
 * skipped instead of substituting mocks or declaring a static build green.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  // No browser process is launched for ordinary unit-test runs. Runtime E2E
  // needs a real API and PostgreSQL, enabled explicitly by the operator.
  testIgnore: runtimeEnabled ? [] : ["**/*.spec.ts"],
  timeout: 30_000,
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI
    ? [["line"], ["html", { outputFolder: ".cache/playwright/report", open: "never" }]]
    : "list",
  use: {
    ...devices["Desktop Chrome"],
    baseURL: siteURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    { name: "desktop-chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile-chromium", use: { ...devices["Pixel 5"] } },
  ],
  outputDir: ".cache/playwright/results",
});
