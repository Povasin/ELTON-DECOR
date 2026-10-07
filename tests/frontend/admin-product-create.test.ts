import { describe, expect, it } from "vitest";
import { attributesFromRows } from "../../apps/admin/lib/product-form";

describe("admin product creation form", () => {
  it("serializes entered characteristic rows and ignores empty names", () => {
    expect(attributesFromRows([
      { id: 1, name: " Материал ", value: " Керамика " },
      { id: 2, name: "", value: "непоказывать" },
      { id: 3, name: "Размер", value: "25 см" },
    ])).toEqual({ Материал: "Керамика", Размер: "25 см" });
  });
});
