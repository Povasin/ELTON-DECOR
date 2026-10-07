import { expect, test } from "@playwright/test";

const runtimeEnabled = process.env.ELTON_E2E_ENABLED === "1";
const adminRuntimeEnabled = process.env.ELTON_ADMIN_E2E_APPROVED === "1";
const adminBaseURL = process.env.ELTON_ADMIN_E2E_BASE_URL ?? "http://localhost:3001";
const adminEmail = process.env.ELTON_ADMIN_E2E_EMAIL;
const adminPassword = process.env.ELTON_ADMIN_E2E_PASSWORD;
const draftId = process.env.ELTON_ADMIN_E2E_DRAFT_ID ?? "00000000-0000-0000-0000-000000000001";

function skipReason() {
  if (!runtimeEnabled) return "Browser/API/PostgreSQL runtime gate is not enabled";
  if (!adminRuntimeEnabled) return "ADM-01 admin login gate is not approved";
  return "Admin credentials are not provided through the runtime secret store";
}

test.describe("admin protected pages", () => {
  test("draft details do not disclose data before an admin session", async ({ page }) => {
    test.skip(!runtimeEnabled || !adminRuntimeEnabled, skipReason());

    const response = await page.request.get(
      `${adminBaseURL}/api/v1/admin/checkout-drafts/${draftId}`,
    );
    expect([401, 403]).toContain(response.status());

    await page.goto(`${adminBaseURL}/drafts/${draftId}`);
    await expect(page).toHaveURL(/\/login\?next=/);
  });

  test("an approved admin can reach product and draft detail pages", async ({ page }) => {
    test.skip(!runtimeEnabled || !adminRuntimeEnabled || !adminEmail || !adminPassword, skipReason());

    await page.goto(`${adminBaseURL}/login?next=%2Fproducts`);
    await page.getByLabel("Email").fill(adminEmail!);
    await page.getByLabel("Пароль").fill(adminPassword!);
    await page.getByRole("button", { name: "Войти" }).click();
    await expect(page).toHaveURL(/\/products$/);

    await page.goto(`${adminBaseURL}/products`);
    await expect(page.locator("main")).toBeVisible();
    const productDetailLink = page.locator('a[href^="/products/"]').first();
    if (await productDetailLink.count()) {
      await productDetailLink.click();
      await expect(page).toHaveURL(/\/products\/[^/]+$/);
      await expect(page.locator("main")).toBeVisible();
    }
    await page.goto(`${adminBaseURL}/drafts/${draftId}`);
    await expect(page.locator("main")).toBeVisible();
  });
});
