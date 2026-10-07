import { describe, expect, it } from "vitest";
import { isProductVersionConflict, recoverProductConflict, saveProductDraft } from "../../apps/admin/lib/product-save";

const image = { id: "image", type: "image" as const, url: "/one.webp", alt_text: "", position: 0 };
const video = { id: "video", type: "video" as const, url: "/one.mp4", alt_text: "", position: 1 };

describe("admin global product save", () => {
  it("replaces stale form values and clears media drafts when recovering a version conflict", async () => {
    let form = { id: "p", title: "Unsaved stale title", version: 1, media: [image] };
    let staged = ["stale-video"];
    const authoritative = { id: "p", title: "Changed elsewhere", version: 5, media: [video] };
    const recovered = await recoverProductConflict("p", async () => authoritative, (loaded) => { form = loaded; }, () => { staged = []; });
    expect(recovered).toBe(true);
    expect(form).toEqual(authoritative);
    expect(staged).toEqual([]);
  });

  it("keeps saving blocked if a conflict cannot be refreshed", async () => {
    let form = { title: "Stale" };
    const pendingFile = new Blob(["local video bytes"], { type: "video/mp4" });
    let pendingFiles = [pendingFile];
    let draftsCleared = false;
    const recovered = await recoverProductConflict("p", async () => { throw Error("offline"); }, (loaded) => { form = loaded; }, () => { draftsCleared = true; pendingFiles = []; });
    expect(recovered).toBe(false);
    expect(form).toEqual({ title: "Stale" });
    expect(draftsCleared).toBe(false);
    expect(pendingFiles[0]).toBe(pendingFile);
    expect(await pendingFiles[0].text()).toBe("local video bytes");
  });

  it("rejects a second total video before any mutation or upload", async () => {
    let operations = 0;
    await expect(saveProductDraft({
      product: { id: "p", version: 1, media: [video] },
      commands: [{ run: async () => { operations++; } }], removals: [],
      additions: [{ id: "pending-video", type: "video", file: new Blob(["video"]), filename: "new.mp4" }],
      api: { read: async () => { operations++; return { id: "p", version: 2, media: [video] }; }, remove: async () => { operations++; }, upload: async () => { operations++; return video; } },
    })).rejects.toThrow("одно видео");
    expect(operations).toBe(0);
  });

  it("retains the last acknowledged version when a later non-conflict mutation fails", async () => {
    let visible = { id: "p", version: 1, media: [image], title: "Before" };
    let reads = 0;
    await expect(saveProductDraft({
      product: visible,
      commands: [
        { run: async () => ({ ...visible, version: 2, title: "Acknowledged" }) },
        { run: async () => { throw Error("price rejected"); } },
      ], additions: [], removals: [],
      api: { read: async () => { reads++; return { ...visible, version: 5, title: "Changed elsewhere" }; }, remove: async () => {}, upload: async () => image },
      onProduct: (product) => { visible = product; },
    })).rejects.toThrow("price rejected");
    expect(visible.version).toBe(2);
    expect(visible.title).toBe("Acknowledged");
    expect(reads).toBe(0);
  });

  it("distinguishes version conflicts from unavailable video capability", () => {
    expect(isProductVersionConflict({ status: 409, problem: { code: "VERSION_CONFLICT" } })).toBe(true);
    expect(isProductVersionConflict({ status: 409, problem: {} })).toBe(true);
    expect(isProductVersionConflict({ status: 409, problem: { code: "CAPABILITY_DISABLED" } })).toBe(false);
  });
  it("retains existing media through partial mutation responses and refreshes the server version", async () => {
    let server = { id: "p", version: 1, media: [image, video], title: "Before" };
    const visible: typeof server[] = [];
    const result = await saveProductDraft({
      product: server,
      commands: [{ run: async (current) => { expect(current.version).toBe(1); server = { ...server, title: "After", version: 2 }; return { id: "p", title: "After", version: 2 }; } }],
      additions: [], removals: [],
      api: { read: async () => server, upload: async () => { throw Error("unused"); }, remove: async () => { throw Error("unused"); } },
      onProduct: (product) => visible.push(product as typeof server),
    });
    expect(visible.every((product) => product.media.length === 2)).toBe(true);
    expect(visible.length).toBeGreaterThan(0);
    expect(result.title).toBe("After");
    expect(result).toEqual(server);
  });

  it("uses the refreshed version for each removal and upload and keeps images before video", async () => {
    let server = { id: "p", version: 3, media: [image, video] };
    const submitted: Array<{ version: number; position: number }> = [];
    const completed: string[] = [];
    const addedVideo = { id: "pending-video", type: "video" as const, file: new Blob(["video"]), filename: "new.mp4" };
    const addedImage = { id: "pending-image", type: "image" as const, file: new Blob(["image"]), filename: "new.webp" };
    const result = await saveProductDraft({
      product: server, commands: [], additions: [addedVideo, addedImage], removals: ["video"],
      api: {
        read: async () => server,
        remove: async (_id, mediaId, version) => { expect(version).toBe(3); server = { ...server, version: 4, media: server.media.filter((media) => media.id !== mediaId) }; },
        upload: async (_id, addition, position, version) => {
          submitted.push({ position, version });
          const media = { ...image, id: addition.id, type: addition.type, position };
          server = { ...server, version: version + 1, media: [...server.media, media] };
          return media;
        },
      },
      onAdditionSaved: (id) => completed.push(id),
    });
    expect(submitted).toEqual([{ position: 1, version: 4 }, { position: 2, version: 5 }]);
    expect(result.media.map((media) => media.id)).toEqual(["image", "pending-image", "pending-video"]);
    expect(completed).toEqual(["pending-image", "pending-video"]);
  });

  it("marks a confirmed upload complete even when the subsequent refresh fails", async () => {
    const completed: string[] = [];
    const visible: Array<{ media: typeof image[] }> = [];
    await expect(saveProductDraft({
      product: { id: "p", version: 1, media: [image] }, commands: [], removals: [],
      additions: [{ id: "pending", type: "image", file: new Blob(["new"]), filename: "new.webp" }],
      api: { read: async () => { throw Error("refresh failed"); }, remove: async () => {}, upload: async () => ({ ...image, id: "new", position: 1 }) },
      onAdditionSaved: (id) => completed.push(id), onProduct: (product) => visible.push(product),
    })).rejects.toThrow("refresh failed");
    expect(completed).toEqual(["pending"]);
    expect(visible.at(-1)?.media.map((media) => media.id)).toEqual(["image", "new"]);
  });
});
