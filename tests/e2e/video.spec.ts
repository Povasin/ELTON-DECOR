import { expect, test } from "@playwright/test";

/**
 * Video acceptance is deliberately opt-in.  A passing local foundation run
 * must not imply that the MP4 decoder/transcode capability is available.
 * Enable only against a runtime seeded with a synthetic, clean MP4:
 *   ELTON_E2E_ENABLED=1
 *   ELTON_VIDEO_E2E_ENABLED=1
 *   ELTON_VIDEO_E2E_SLUG=<synthetic product slug>
 */
const runtimeEnabled = process.env.ELTON_E2E_ENABLED === "1";
const videoRuntimeEnabled = process.env.ELTON_VIDEO_E2E_ENABLED === "1";
const videoSlug = process.env.ELTON_VIDEO_E2E_SLUG;

function skipReason() {
  if (!runtimeEnabled) return "Browser/API/PostgreSQL runtime gate is not enabled";
  if (!videoRuntimeEnabled) return "MP4 video acceptance gate is not enabled";
  return "A synthetic seeded product slug is not configured";
}

test.describe("published MP4 media", () => {
  test("product page exposes a playable clean video", async ({ page }) => {
    test.skip(!runtimeEnabled || !videoRuntimeEnabled || !videoSlug, skipReason());

    await page.goto(`/products/${encodeURIComponent(videoSlug!)}`);
    const video = page.locator("video").first();
    await expect(video).toHaveCount(1);
    await expect(video).toBeVisible();
    await expect(video).toHaveAttribute("controls", "");

    const source = await video.evaluate((element) => {
      const player = element as HTMLVideoElement;
      return {
        currentSrc: player.currentSrc,
        readyState: player.readyState,
        networkState: player.networkState,
        error: player.error?.code ?? null,
      };
    });

    expect(source.currentSrc).toMatch(/\/api\/v1\/media\/clean\//);
    expect(source.currentSrc).not.toMatch(/quarantine|\.upload(?:$|[?#])/i);
    expect(source.error).toBeNull();
    expect(source.readyState).toBeGreaterThanOrEqual(1); // HAVE_METADATA
  });
});
