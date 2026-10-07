import { afterEach, describe, expect, it, vi } from "vitest";
import { api, resetAdminSessionForUnauthorized } from "../../packages/api-client/src/index";

const session = {
  id: "00000000-0000-0000-0000-000000000001",
  email: "owner@example.test",
  permissions: ["catalog.read", "catalog.write", "drafts.read"],
  csrf_token: "csrf-for-this-session",
  expires_at: "2026-10-07T12:00:00Z",
};

afterEach(() => {
  vi.unstubAllGlobals();
  resetAdminSessionForUnauthorized();
});

describe("admin API client", () => {
  it("loads an admin product detail and forwards list filters", async () => {
    const product = { id: "product-1", title: "Ваза", version: 4 };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(product), { status: 200, headers: { "content-type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [product], next_cursor: null }), { status: 200, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.adminProduct("product-1")).resolves.toEqual(product);
    await expect(api.adminProducts({ q: "ваза", limit: 10, cursor: "next" })).resolves.toMatchObject({ items: [product] });

    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/admin/products/product-1");
    expect(fetchMock.mock.calls[1][0]).toBe("/api/v1/admin/products?q=%D0%B2%D0%B0%D0%B7%D0%B0&limit=10&cursor=next");
  });

  it("sends product mutations with admin CSRF and If-Match", async () => {
    const product = { id: "product-1", title: "Новая ваза", version: 5 };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(session), { status: 200, headers: { "content-type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(product), { status: 200, headers: { "content-type": "application/json", etag: '"5"' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(product), { status: 200, headers: { "content-type": "application/json", etag: '"6"' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ version_id: "bundle-1", version: 2, components: [] }), { status: 200, headers: { "content-type": "application/json", etag: '"7"' } }));
    vi.stubGlobal("fetch", fetchMock);
    await api.adminSession();

    await api.updateAdminProduct("product-1", { title: "Новая ваза" }, 4);
    await api.setAdminSitePrice("product-1", { price: { amount_minor: "12500", currency: "RUB" } }, 5);
    await api.replaceAdminBundle("product-1", { components: [{ product_id: "component-1", quantity: 2 }] }, 6);

    for (const [index, expectedPath] of [
      "/api/v1/admin/products/product-1",
      "/api/v1/admin/products/product-1/site-price",
      "/api/v1/admin/products/product-1/bundle",
    ].entries()) {
      expect(fetchMock.mock.calls[index + 1][0]).toBe(expectedPath);
      const headers = new Headers(fetchMock.mock.calls[index + 1][1].headers);
      expect(headers.get("x-csrf-token")).toBe(session.csrf_token);
      expect(headers.get("if-match")).toBe(`"${index + 4}"`);
      expect(headers.get("content-type")).toBe("application/json");
    }
  });

  it("uses multipart for media upload and keeps admin CSRF/version headers", async () => {
    const media = { id: "media-1", type: "image", url: "/media/image.webp", alt_text: "Ваза", position: 0 };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(session), { status: 200, headers: { "content-type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(media), { status: 201, headers: { "content-type": "application/json" } }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    await api.adminSession();

    await api.uploadAdminMedia("product-1", new Blob(["image"], { type: "image/png" }), { alt_text: "Ваза", position: 2 }, 4, "vase.png");
    await api.deleteAdminMedia("product-1", "media-1", 5);

    const uploadHeaders = new Headers(fetchMock.mock.calls[1][1].headers);
    expect(uploadHeaders.get("x-csrf-token")).toBe(session.csrf_token);
    expect(uploadHeaders.get("if-match")).toBe('"4"');
    expect(uploadHeaders.get("content-type")).toBeNull();
    const body = fetchMock.mock.calls[1][1].body as FormData;
    expect(body).toBeInstanceOf(FormData);
    expect(body.get("alt_text")).toBe("Ваза");
    expect(body.get("position")).toBe("2");
    expect(body.get("file")).toBeInstanceOf(Blob);

    const deleteHeaders = new Headers(fetchMock.mock.calls[2][1].headers);
    expect(deleteHeaders.get("x-csrf-token")).toBe(session.csrf_token);
    expect(deleteHeaders.get("if-match")).toBe('"5"');
  });

  it("reports browser upload progress for media uploads", async () => {
    const media = { id: "media-2", type: "video", url: "/media/video.mp4", alt_text: "", position: 0 };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(session), { status: 200, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    const progressSamples: number[] = [];
    const xhr = {
      upload: { onprogress: null as ((event: ProgressEvent) => void) | null },
      open: vi.fn(),
      setRequestHeader: vi.fn(),
      send: vi.fn(function (this: typeof xhr) {
        this.upload.onprogress?.({ lengthComputable: true, loaded: 50, total: 100 } as ProgressEvent);
        this.status = 201;
        this.responseText = JSON.stringify(media);
        this.onload?.();
      }),
      status: 0,
      responseText: "",
      onload: null as (() => void) | null,
      onerror: null as (() => void) | null,
      onabort: null as (() => void) | null,
      withCredentials: false,
    };
    vi.stubGlobal("XMLHttpRequest", vi.fn(() => xhr));

    await api.adminSession();
    await expect(api.uploadAdminMedia("product-1", new Blob(["video"], { type: "video/mp4" }), {}, 4, "video.mp4", (value) => progressSamples.push(value))).resolves.toEqual(media);

    expect(progressSamples).toEqual([0, 50, 100]);
    expect(xhr.open).toHaveBeenCalledWith("POST", "/api/v1/admin/products/product-1/media", true);
    expect(xhr.withCredentials).toBe(true);
    expect(xhr.setRequestHeader).toHaveBeenCalledWith("x-csrf-token", session.csrf_token);
    expect(xhr.setRequestHeader).toHaveBeenCalledWith("if-match", '"4"');
  });

  it("loads paged draft summaries and an individual draft", async () => {
    const draft = { id: "draft-1", state: "saved", channel: "site", created_at: "2026-10-07T10:00:00Z", goods_total: { amount_minor: "10000", currency: "RUB" }, contact: { phone: "+79990000000" }, address: { city: "Москва" } };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [draft], next_cursor: "cursor-2" }), { status: 200, headers: { "content-type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(draft), { status: 200, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    await api.adminDrafts({ cursor: "cursor-1", created_from: "2026-10-01T00:00:00Z", created_to: "2026-10-07T23:59:59Z" });
    await api.adminDraft("draft-1");

    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/admin/checkout-drafts?cursor=cursor-1&created_from=2026-10-01T00%3A00%3A00Z&created_to=2026-10-07T23%3A59%3A59Z");
    expect(fetchMock.mock.calls[1][0]).toBe("/api/v1/admin/checkout-drafts/draft-1");
  });
});
