import { describe, expect, it } from "vitest";
import { forwardHeaders as storefrontHeaders, upstreamUrl as storefrontUrl } from "../../apps/storefront/lib/proxy";
import { forwardHeaders as adminHeaders, upstreamUrl as adminUrl } from "../../apps/admin/lib/proxy";

describe("same-origin API proxy boundaries", () => {
  it("builds a fixed server configured upstream and keeps only the request query", () => {
    const url = storefrontUrl("http://localhost:3000/api/v1/products?q=vase", ["products"], "http://127.0.0.1:8000");
    expect(url.toString()).toBe("http://127.0.0.1:8000/api/v1/products?q=vase");
    expect(url.toString()).not.toContain("localhost:3000");
    expect(() => adminUrl("http://localhost:3001/api/v1/products?upstream=https://evil.invalid", ["products"], undefined)).toThrow("ELTON_API_URL");
  });

  it("forwards trust and session headers but never authorization or client upstream", () => {
    const incoming = new Headers({ cookie: "elton_guest=opaque; elton_admin=opaque-admin-proof", origin: "http://localhost:3000", "x-csrf-token": "csrf", "x-request-id": "request", authorization: "Bearer secret", "x-upstream": "https://evil.invalid" });
    for (const result of [storefrontHeaders(incoming), adminHeaders(incoming)]) {
      expect(result.get("cookie")).toBe("elton_guest=opaque; elton_admin=opaque-admin-proof");
      expect(result.get("origin")).toBe("http://localhost:3000");
      expect(result.get("x-csrf-token")).toBe("csrf");
      expect(result.get("x-request-id")).toBe("request");
      expect(result.get("authorization")).toBeNull();
      expect(result.get("x-upstream")).toBeNull();
    }
  });
});
