import { describe, expect, it } from "vitest";
import { appendAdminMedia, removeAdminMedia, sortAdminMedia, stageAdminMedia, hasAtMostOneVideo, type AdminMediaLike } from "../../apps/admin/lib/media";

const first: AdminMediaLike = {
  id: "media-1",
  type: "image",
  url: "/media/one.webp",
  alt_text: "Первое изображение",
  position: 0,
};

const second: AdminMediaLike = {
  id: "media-2",
  type: "image",
  url: "/media/two.webp",
  alt_text: "Второе изображение",
  position: 1,
};

describe("admin media state reconciliation", () => {
  it("rejects an additional video until the saved video is staged for deletion", () => {
    const savedVideo = { ...second, id: "saved-video", type: "video" as const };
    const newVideo = { ...second, id: "new-video", type: "video" as const };
    expect(hasAtMostOneVideo([first, savedVideo], [], [newVideo])).toBe(false);
    expect(hasAtMostOneVideo([first, savedVideo], [savedVideo.id], [newVideo])).toBe(true);
    expect(hasAtMostOneVideo([], [], [savedVideo, newVideo])).toBe(false);
  });
  it("replaces an earlier pending video while preserving all pending images", () => {
    const oldVideo = { ...second, id: "old-video", type: "video" as const };
    const newVideo = { ...second, id: "new-video", type: "video" as const };
    expect(stageAdminMedia([first, oldVideo, second], [newVideo])).toEqual([first, second, newVideo]);
    expect(stageAdminMedia([first, oldVideo], [])).toEqual([first, oldVideo]);
  });

  it("retains only the final video even if a selection includes multiple videos", () => {
    const videos = ["v1", "v2"].map((id) => ({ ...second, id, type: "video" as const }));
    expect(stageAdminMedia([first], videos).map((item) => item.id)).toEqual([first.id, "v2"]);
    expect(stageAdminMedia(videos, [first, second]).map((item) => item.id)).toEqual(["v2", first.id, second.id]);
  });
  it("appends a successfully uploaded media item without losing existing items", () => {
    expect(appendAdminMedia([first], second)).toEqual([first, second]);
  });

  it("replaces an item with the same id instead of duplicating it", () => {
    const updated = { ...first, url: "/media/one-new.webp" };
    expect(appendAdminMedia([first, second], updated)).toEqual([updated, second]);
  });

  it("removes the deleted item immediately and keeps the remaining order", () => {
    expect(removeAdminMedia([first, second], first.id)).toEqual([second]);
    expect(removeAdminMedia([first], first.id)).toEqual([]);
  });

  it("puts all images before video even when the server positions are mixed", () => {
    const video = { ...second, id: "video-1", type: "video" as const, position: 0 };
    expect(sortAdminMedia([video, second, first]).map((item) => item.id)).toEqual(["media-1", "media-2", "video-1"]);
  });
});
