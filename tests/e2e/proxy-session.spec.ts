import { expect, test } from "@playwright/test";

const runtimeEnabled = process.env.ELTON_E2E_ENABLED === "1";
const adminBaseURL = process.env.ELTON_ADMIN_E2E_BASE_URL ?? "http://localhost:3001";

test.describe("same-origin session and scope boundaries", () => {
  test.beforeEach(async ({}, testInfo) => {
    testInfo.annotations.push({
      type: "gate",
      description: "Requires a running storefront, admin proxy, API and seeded PostgreSQL.",
    });
    test.skip(!runtimeEnabled, "Browser/API/PostgreSQL runtime gate is not enabled");
  });

  test("guest requests cannot use the admin session or draft scope", async ({ page }) => {
    const session = await page.request.get(`${adminBaseURL}/api/v1/admin/session`);
    expect([401, 403]).toContain(session.status());

    const drafts = await page.request.get(`${adminBaseURL}/api/v1/admin/checkout-drafts`);
    expect([401, 403]).toContain(drafts.status());
  });

  test("storefront product and local draft pages remain reachable", async ({ page }) => {
    await page.goto("/catalog");
    await expect(page.locator("main")).toBeVisible();

    await page.goto("/drafts");
    await expect(page.locator("main")).toBeVisible();
  });
});
