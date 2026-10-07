import { expect, test } from "@playwright/test";

const runtimeEnabled = process.env.ELTON_E2E_ENABLED === "1";
const gallerySlug = process.env.ELTON_GALLERY_E2E_SLUG;

test.describe("product media gallery", () => {
  test("selects media, opens the viewer and restores focus after Escape", async ({ page }) => {
    test.skip(!runtimeEnabled || !gallerySlug, "Gallery E2E requires a seeded product with at least two clean media items");

    await page.goto(`/products/${encodeURIComponent(gallerySlug!)}`);
    const thumbnails = page.locator(".gallery-thumbnail");
    await expect(thumbnails.first()).toBeVisible({ timeout: 10_000 });
    expect(await thumbnails.count()).toBeGreaterThanOrEqual(2);
    await expect(thumbnails.first()).toHaveAttribute("aria-pressed", "true");

    await thumbnails.nth(1).click();
    await expect(thumbnails.nth(1)).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: "Открыть медиа на весь экран" }).click();

    const dialog = page.getByRole("dialog", { name: /Полноэкранная галерея/i });
    await expect(dialog).toBeVisible();
    await page.keyboard.press("ArrowLeft");
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(thumbnails.nth(1)).toBeFocused();
  });
});
