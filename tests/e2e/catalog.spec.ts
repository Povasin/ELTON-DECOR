import { expect, test } from "@playwright/test";

const runtimeEnabled = process.env.ELTON_E2E_ENABLED === "1";

test.describe("catalog search and sorting", () => {
  test.beforeEach(async ({}, testInfo) => {
    testInfo.annotations.push({
      type: "gate",
      description: "Requires ELTON_E2E_ENABLED=1, local API and seeded PostgreSQL.",
    });
    test.skip(!runtimeEnabled, "Browser/API/PostgreSQL runtime gate is not enabled");
  });

  test("searches, sorts and exposes an empty result", async ({ page }) => {
    await page.goto("/catalog");
    await expect(page.getByLabel("Поиск по названию или SKU")).toBeVisible();

    await page.getByLabel("Поиск по названию или SKU").fill("Демонстрационная");
    await page.getByRole("button", { name: "Найти" }).click();
    await expect(page).toHaveURL(/\?q=/);
    await expect(page.locator('a[href^="/products/"]').first()).toBeVisible();

    await page.getByLabel("Сортировка").selectOption("price_desc");
    await expect(page).toHaveURL(/sort=price_desc/);

    await page.getByLabel("Поиск по названию или SKU").fill("товар-которого-точно-нет");
    await page.getByRole("button", { name: "Найти" }).click();
    await expect(page.getByText("Ничего не найдено")).toBeVisible();
    await expect(page.getByText(/По запросу «товар-которого-точно-нет» ничего не найдено/)).toBeVisible();
  });
});
