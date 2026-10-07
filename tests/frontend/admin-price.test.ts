import { describe, expect, it } from "vitest";
import { formatPriceInput, parseRublesToMinor } from "../../apps/admin/lib/price";

describe("admin price input", () => {
  it("converts whole rubles to minor units", () => {
    expect(parseRublesToMinor("150")).toBe("15000");
  });

  it("accepts decimal comma, decimal point and grouped spaces", () => {
    expect(parseRublesToMinor("150,50")).toBe("15050");
    expect(parseRublesToMinor("150.5")).toBe("15050");
    expect(parseRublesToMinor("1 250,90")).toBe("125090");
  });

  it("rejects more than two fractional digits", () => {
    expect(parseRublesToMinor("150,125")).toBeNull();
  });

  it("formats stored minor units as rubles for the input", () => {
    expect(formatPriceInput("15000")).toBe("150");
    expect(formatPriceInput("15050")).toBe("150.50");
    expect(formatPriceInput("150")).toBe("1.50");
  });
});
