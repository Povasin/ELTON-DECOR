import { describe, expect, it } from "vitest";
import { getOriginalPrice, getProductAttributes, getVariantProducts, isDiscounted } from "../../apps/storefront/lib/product-fields";

const price = (amount_minor: string) => ({ amount_minor, currency: "RUB" as const });

describe("storefront product commerce fields", () => {
  it("uses the original price only when it is higher than the current price", () => {
    const product = { price: price("15000"), original_price: price("20000") };
    expect(getOriginalPrice(product)).toEqual(price("20000"));
    expect(isDiscounted(product)).toBe(true);
    expect(isDiscounted({ price: price("20000"), original_price: price("15000") })).toBe(false);
  });

  it("normalizes both the existing object shape and editor rows", () => {
    expect(getProductAttributes({ attributes: { Материал: "Керамика", Высота: 25 } })).toEqual([
      { name: "Материал", value: "Керамика" },
      { name: "Высота", value: "25" },
    ]);
    expect(getProductAttributes({ attributes: [{ name: "Цвет", value: "Белый" }] })).toEqual([
      { name: "Цвет", value: "Белый" },
    ]);
  });

  it("resolves variant cards from embedded products or public catalog candidates", () => {
    const candidate = { id: "variant", slug: "variant", title: "Белый", sku: "V", type: "single" as const, price: price("10000"), version: 1 };
    const product = { related_product_ids: [candidate.id], attributes: {}, related_products: [] } as never;
    expect(getVariantProducts(product, [candidate])).toEqual([candidate]);
    expect(getVariantProducts({ ...product, related_products: [candidate] }, [])).toEqual([candidate]);
  });
});
