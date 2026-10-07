import { describe, expect, it } from "vitest";
import { nextGalleryIndex, previousGalleryIndex, sortGalleryMedia, type GalleryMedia } from "../../apps/storefront/lib/gallery";

const media: GalleryMedia[] = [
  { id: "video", type: "video", url: "/api/v1/media/clean/video.mp4", alt_text: "Видео", position: 0 },
  { id: "second", type: "image", url: "/api/v1/media/clean/second.webp", alt_text: "Второй кадр", position: 1 },
  { id: "first", type: "image", url: "/api/v1/media/clean/first.webp", alt_text: "Первый кадр", position: 0 },
];

describe("product gallery state", () => {
  it("keeps images first and video last without mutating the source", () => {
    const sorted = sortGalleryMedia(media);

    expect(sorted.map((item) => item.id)).toEqual(["first", "second", "video"]);
    expect(media.map((item) => item.id)).toEqual(["video", "second", "first"]);
  });

  it("cycles forward and backward through the media items", () => {
    expect(nextGalleryIndex(0, media.length)).toBe(1);
    expect(nextGalleryIndex(media.length - 1, media.length)).toBe(0);
    expect(previousGalleryIndex(2, media.length)).toBe(1);
    expect(previousGalleryIndex(0, media.length)).toBe(2);
  });

  it("keeps an empty gallery at index zero", () => {
    expect(nextGalleryIndex(0, 0)).toBe(0);
    expect(previousGalleryIndex(0, 0)).toBe(0);
  });
});
