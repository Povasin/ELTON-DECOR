import type { Money, ProductDetail, ProductSummary } from "@elton/api-client";

/**
 * Fields introduced by the catalog editor are kept optional here so the
 * storefront remains compatible with older published product responses while
 * the API contract is rolled out.
 */
export type ProductPriceFields = {
  original_price?: Money | null;
  compare_at_price?: Money | null;
};

export type ProductWithCatalogFields = ProductDetail & ProductPriceFields & {
  related_products?: ProductSummary[];
  relatedProducts?: ProductSummary[];
};

export type ProductSummaryWithCatalogFields = ProductSummary & ProductPriceFields;

export type ProductAttribute = { name: string; value: string };

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function asText(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return "";
  return String(value);
}

export function getOriginalPrice(product: ProductPriceFields): Money | null {
  return product.original_price ?? product.compare_at_price ?? null;
}

export function isDiscounted(product: ProductPriceFields & { price: Money }): boolean {
  const original = getOriginalPrice(product);
  return Boolean(original && BigInt(original.amount_minor) > BigInt(product.price.amount_minor));
}

export function getProductAttributes(product: { attributes?: unknown }): ProductAttribute[] {
  const attributes = product.attributes;
  if (Array.isArray(attributes)) {
    return attributes.flatMap((item) => {
      const record = asRecord(item);
      if (!record) return [];
      const name = asText(record.name ?? record.key ?? record.title).trim();
      const value = asText(record.value).trim();
      return name && value ? [{ name, value }] : [];
    });
  }

  const record = asRecord(attributes);
  if (!record) return [];
  return Object.entries(record).flatMap(([name, value]) => {
    const text = asText(value).trim();
    return name.trim() && text ? [{ name: name.trim(), value: text }] : [];
  });
}

export function getVariantProducts(
  product: ProductWithCatalogFields,
  candidates: ProductSummary[] = [],
): ProductSummary[] {
  const embedded = product.related_products ?? product.relatedProducts ?? [];
  if (embedded.length) return embedded;

  const relatedIds = new Set(product.related_product_ids ?? []);
  return candidates.filter((candidate) => relatedIds.has(candidate.id));
}

/** @deprecated The API field is retained for compatibility; these are variants, not recommendations. */
export const getRelatedProducts = getVariantProducts;
