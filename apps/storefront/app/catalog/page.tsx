import type { Metadata } from "next";
import CatalogClient from "./catalog-client";

export const metadata: Metadata = { title: "Каталог", description: "Каталог предметов Elton Decor.", alternates: { canonical: "/catalog" } };

export default async function CatalogPage({ searchParams }: { searchParams: Promise<{ category?: string | string[]; q?: string | string[]; sort?: string | string[] }> }) {
  const query = await searchParams;
  const category = typeof query.category === "string" ? query.category : "";
  const text = typeof query.q === "string" ? query.q : "";
  const sort = query.sort === "price_asc" || query.sort === "price_desc" ? query.sort : "title_asc";
  return <CatalogClient initialCategory={category} initialQuery={text} initialSort={sort} />;
}
