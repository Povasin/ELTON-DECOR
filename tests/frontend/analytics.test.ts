import { describe, expect, it } from "vitest";
import { sanitizeAnalyticsEvent } from "../../packages/analytics/src";

describe("analytics event schema", () => {
  it("keeps catalog search fields and removes personal data", () => {
    expect(sanitizeAnalyticsEvent({
      name: "search",
      query: "ваза",
      category: "vases",
      phone: "+79990000000",
      email: "buyer@example.test",
    })).toEqual({ name: "search", query: "ваза", category: "vases" });
  });

  it("does not allow a client purchase event", () => {
    expect(sanitizeAnalyticsEvent({ name: "purchase", order_id: "draft-1" })).toBeNull();
  });
});
