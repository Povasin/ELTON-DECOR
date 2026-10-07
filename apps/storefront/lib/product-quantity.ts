export type CartItemQuantity = { product_id: string; quantity: number };

export function cartQuantity(items: readonly CartItemQuantity[], productId: string): number {
  return items.find((item) => item.product_id === productId)?.quantity ?? 0;
}

export type QuantityChange = { kind: "set"; quantity: number } | { kind: "remove" };

export function nextQuantityChange(quantity: number, direction: 1 | -1): QuantityChange {
  if (direction === -1 && quantity <= 1) return { kind: "remove" };
  return { kind: "set", quantity: quantity + direction };
}
