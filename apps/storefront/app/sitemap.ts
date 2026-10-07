import type { MetadataRoute } from "next";
import type { ProductPage } from "@elton/api-client";
import { absoluteSiteUrl } from "../lib/site";

export const dynamic = "force-dynamic";
const PAGE_SIZE = 100;
const MAX_PAGES = 100;

async function products(): Promise<ProductPage["items"]> {
  const base = process.env.ELTON_API_URL;
  if (!base) return [];
  const items: ProductPage["items"] = [];
  const seenSlugs = new Set<string>();
  const seenCursors = new Set<string>();
  let cursor: string | undefined;
  try {
    for (let page = 0; page < MAX_PAGES; page += 1) {
      const url = new URL("/api/v1/products", base);
      url.searchParams.set("limit", String(PAGE_SIZE));
      if (cursor) url.searchParams.set("cursor", cursor);
      const response = await fetch(url, { cache: "no-store" });
      if (!response.ok) return items;
      const result = await response.json() as ProductPage;
      for (const item of result.items) {
        if (!seenSlugs.has(item.slug)) { seenSlugs.add(item.slug); items.push(item); }
      }
      const next = result.next_cursor;
      if (!next || seenCursors.has(next)) break;
      seenCursors.add(next);
      cursor = next;
    }
    return items;
  } catch { return items; }
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const entries: MetadataRoute.Sitemap = [
    { url: absoluteSiteUrl("/"), changeFrequency: "weekly", priority: 1 },
    { url: absoluteSiteUrl("/catalog"), changeFrequency: "daily", priority: .8 },
    { url: absoluteSiteUrl("/about"), changeFrequency: "monthly", priority: .4 },
  ];
  const items = await products();
  return entries.concat(items.map((product) => ({ url: absoluteSiteUrl(`/products/${encodeURIComponent(product.slug)}`), changeFrequency: "weekly" as const, priority: .7 })));
}
