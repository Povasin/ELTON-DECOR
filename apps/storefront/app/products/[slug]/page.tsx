import type { Metadata } from "next";
import type { ProductDetail } from "@elton/api-client";
import ProductClient from "./product-client";
import { siteUrl } from "../../../lib/site";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const fallback = { title: "Товар", alternates: { canonical: `/products/${slug}` } } satisfies Metadata;
  const base = process.env.ELTON_API_URL;
  if (!base) return fallback;
  try {
    const response = await fetch(new URL(`/api/v1/products/by-slug/${encodeURIComponent(slug)}`, base), { cache: "no-store" });
    if (!response.ok) return fallback;
    const product = await response.json() as { title?: string; description?: string };
    return { title: product.title ?? fallback.title, description: product.description, alternates: { canonical: `/products/${slug}` } };
  } catch { return fallback; }
}

async function fetchProduct(slug: string): Promise<ProductDetail | null> {
  const base = process.env.ELTON_API_URL;
  if (!base) return null;
  try {
    const response = await fetch(new URL(`/api/v1/products/by-slug/${encodeURIComponent(slug)}`, base), { cache: "no-store" });
    return response.ok ? await response.json() as ProductDetail : null;
  } catch { return null; }
}

function minorToDecimal(amountMinor: string): string {
  const minor = BigInt(amountMinor);
  const major = minor / 100n;
  const cents = (minor % 100n).toString().padStart(2, "0");
  return `${major}.${cents}`;
}

function safeAbsoluteUrl(value: string, base: URL): string | null {
  try { return new URL(value, base).toString(); } catch { return null; }
}

function ProductStructuredData({ product, slug }: { product: ProductDetail; slug: string }) {
  const base = siteUrl();
  const productUrl = new URL(`/products/${encodeURIComponent(slug)}`, base).toString();
  const images = product.media.filter((media) => media.type === "image").map((media) => safeAbsoluteUrl(media.url, base)).filter((value): value is string => Boolean(value));
  const productSchema = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.title,
    sku: product.sku,
    ...(product.description ? { description: product.description } : {}),
    ...(images.length ? { image: images } : {}),
    ...(product.categories.length ? { category: product.categories[0].title } : {}),
    url: productUrl,
    offers: { "@type": "Offer", priceCurrency: product.price.currency, price: minorToDecimal(product.price.amount_minor), url: productUrl },
  };
  const breadcrumbItems = [{ "@type": "ListItem", position: 1, name: "Главная", item: base.toString() }, { "@type": "ListItem", position: 2, name: "Каталог", item: new URL("/catalog", base).toString() }];
  if (product.categories[0]) breadcrumbItems.push({ "@type": "ListItem", position: breadcrumbItems.length + 1, name: product.categories[0].title, item: new URL(`/catalog?category=${encodeURIComponent(product.categories[0].slug)}`, base).toString() });
  breadcrumbItems.push({ "@type": "ListItem", position: breadcrumbItems.length + 1, name: product.title, item: productUrl });
  const breadcrumbSchema = { "@context": "https://schema.org", "@type": "BreadcrumbList", itemListElement: breadcrumbItems };
  const json = JSON.stringify([productSchema, breadcrumbSchema]).replace(/</g, "\\u003c");
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: json }} />;
}

export default async function ProductPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const product = await fetchProduct(slug);
  return <><>{product && <ProductStructuredData product={product} slug={slug} />}</><ProductClient initialProduct={product} /></>;
}
