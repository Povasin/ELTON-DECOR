import { expect, test } from "@playwright/test";

const runtimeEnabled = process.env.ELTON_E2E_ENABLED === "1";

async function putProductInCart(page: import("@playwright/test").Page) {
  await page.goto("/catalog");
  const product = page.locator('a[href^="/products/"]').first();
  await expect(product).toBeVisible();
  await product.click();
  await page.getByRole("button", { name: "Добавить в корзину" }).click();
  await expect(page.getByText("Товар в корзине. Можно изменить количество или перейти в корзину.")).toBeVisible();
}

async function fillCheckout(page: import("@playwright/test").Page) {
  await page.getByLabel("Телефон").fill("+79990000000");
  await page.getByLabel("Город").fill("Москва");
  await page.getByLabel("Адрес").fill("Тестовая улица, 1");
}

test.describe("checkout retry after a lost response", () => {
  test("reuses the saved command after reload instead of creating a duplicate", async ({ page }) => {
    test.skip(!runtimeEnabled, "Browser/API/PostgreSQL runtime gate is not enabled");

    await putProductInCart(page);
    await page.goto("/checkout");
    await expect(page.getByRole("heading", { name: "Контакты и адрес" })).toBeVisible();
    await fillCheckout(page);

    await page.route("**/api/v1/checkout-drafts", async (route) => {
      await route.fetch();
      await route.abort("connectionaborted");
    });
    await page.getByRole("button", { name: "Сохранить заявку" }).click();
    await expect(page.getByText(/Не удалось сохранить заявку/)).toBeVisible();

    await page.unroute("**/api/v1/checkout-drafts");
    await page.reload();
    await expect(page.getByRole("heading", { name: "Контакты и адрес" })).toBeVisible();
    await fillCheckout(page);
    await page.getByRole("button", { name: "Сохранить заявку" }).click();
    await expect(page.getByText("Заявка сохранена; оплата и доставка пока не подключены")).toBeVisible();
  });
});
