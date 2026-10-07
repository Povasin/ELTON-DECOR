import { expect, test } from "@playwright/test";

const runtimeEnabled = process.env.ELTON_E2E_ENABLED === "1";
const adminRuntimeEnabled = process.env.ELTON_ADMIN_E2E_APPROVED === "1";
const adminBaseURL = process.env.ELTON_ADMIN_E2E_BASE_URL ?? "http://localhost:3001";

test.describe("storefront foundation runtime", () => {
  test.beforeEach(async ({ page }, testInfo) => {
    testInfo.annotations.push({
      type: "gate",
      description: "Requires ELTON_E2E_ENABLED=1, a running API and seeded PostgreSQL.",
    });
    test.skip(!runtimeEnabled, "Browser/API/PostgreSQL runtime gate is not enabled");
    await page.goto("/");
  });

  test("home, catalog and product pages are reachable through the storefront", async ({ page }) => {
    await expect(page).toHaveTitle(/Elton Decor/i);
    await page.goto("/catalog");
    await expect(page.locator("main")).toBeVisible();

    const productLink = page.locator('a[href^="/products/"]').first();
    if (await productLink.count()) {
      await productLink.click();
      await expect(page.locator("main")).toBeVisible();
    }
  });

  test("cart and local checkout keep deferred payment and delivery visible", async ({ page }) => {
    await page.goto("/cart");
    await expect(page.locator("main")).toBeVisible();
    await page.goto("/checkout");
    await expect(page.locator("main")).toBeVisible();
    await expect(page.getByText(/оплата|доставка/i).first()).toBeVisible();
  });

  test("same-origin proxy exposes capabilities without provider credentials", async ({ page }) => {
    const response = await page.request.get("/api/v1/capabilities");
    expect(response.status()).toBe(200);
    const capabilities = await response.json();
    expect(capabilities.payment).toBe(false);
    expect(capabilities.delivery).toBe(false);
    expect(capabilities.sms).toBe(false);
    expect(JSON.stringify(capabilities)).not.toMatch(/OZON|SELLER|PERFORMANCE/i);
  });

  test("a random draft id cannot be read without guest ownership", async ({ page }) => {
    const response = await page.request.get(
      "/api/v1/checkout-drafts/00000000-0000-0000-0000-000000000001",
    );
    expect([401, 404]).toContain(response.status());
  });
});
test.describe("admin fail-closed shell", () => {
  test.beforeEach(async ({ page }, testInfo) => {
    testInfo.annotations.push({
      type: "gate",
      description: "Requires a running admin/API runtime and explicit ADM-01 approval.",
    });
    test.skip(!adminRuntimeEnabled, "ADM-01 admin login gate is not approved");
    await page.goto(`${adminBaseURL}/`);
  });

  test("admin pages do not disclose data before a server session", async ({ page }) => {
    await expect(page.locator("main")).toBeVisible();
    await expect(page.getByText(/вход|доступ|сессия|admin/i).first()).toBeVisible();
    await page.goto(`${adminBaseURL}/products`);
    await expect(page.locator("main")).toBeVisible();
  });
});
