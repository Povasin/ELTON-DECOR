import { describe, expect, it } from "vitest";
import { cartQuantity, nextQuantityChange } from "../../apps/storefront/lib/product-quantity";

describe("product page quantity control", () => {
  it("reads the product quantity from the server cart and treats an absent line as zero", () => {
    const items = [
      { product_id: "vase", quantity: 2 },
      { product_id: "flowers", quantity: 1 },
    ];

    expect(cartQuantity(items, "vase")).toBe(2);
    expect(cartQuantity(items, "missing")).toBe(0);
  });

  it("turns plus and minus clicks into set or remove operations", () => {
    expect(nextQuantityChange(2, 1)).toEqual({ kind: "set", quantity: 3 });
    expect(nextQuantityChange(2, -1)).toEqual({ kind: "set", quantity: 1 });
    expect(nextQuantityChange(1, -1)).toEqual({ kind: "remove" });
  });
});
