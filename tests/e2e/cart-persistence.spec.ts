import { expect, test } from "@playwright/test";

const runtimeEnabled = process.env.ELTON_E2E_ENABLED === "1";

test.describe("guest cart persistence", () => {
  test("keeps a guest cart after the browser context is recreated", async ({ browser }) => {
    test.skip(!runtimeEnabled, "Browser/API/PostgreSQL runtime gate is not enabled");

    const first = await browser.newContext();
    const firstPage = await first.newPage();
    await firstPage.goto("/catalog");
    const product = firstPage.locator('a[href^="/products/"]').first();
    await expect(product).toBeVisible();
    await product.click();
    await firstPage.getByRole("button", { name: "Добавить в корзину" }).click();
    await expect(firstPage.getByText(/добавлен в гостевую корзину|в корзине/i)).toBeVisible();
    const storage = await first.storageState();
    await first.close();

    const resumed = await browser.newContext({ storageState: storage });
    const resumedPage = await resumed.newPage();
    await resumedPage.goto("/cart");
    await expect(resumedPage.getByRole("region", { name: "Товары в корзине" })).toBeVisible();
    await expect(resumedPage.getByRole("button", { name: "Увеличить количество" })).toBeVisible();
    await resumed.close();
  });
});
