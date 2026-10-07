"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, formatMoney, type ProductSummary } from "@elton/api-client";
import { EmptyState, Loading } from "@elton/ui";
import { getOriginalPrice, isDiscounted, type ProductSummaryWithCatalogFields } from "../lib/product-fields";

function ProductImage({ product }: { product: ProductSummary }) {
  const [failed, setFailed] = useState(false);
  return <div className={`product-image${product.thumbnail?.url && !failed ? " has-media" : ""}`}>
    {product.thumbnail?.url && !failed ? <img className="product-image-media" src={product.thumbnail.url} alt={product.title} loading="lazy" onError={() => setFailed(true)} /> : <span aria-hidden="true" />}
  </div>;
}

export default function HomeProducts() {
  const [products, setProducts] = useState<ProductSummary[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => { void api.products({ limit: 6 }).then((page) => setProducts(page.items)).catch(() => setFailed(true)); }, []);

  if (failed) return <p className="muted">Товары временно не загрузились. <Link href="/catalog">Открыть каталог →</Link></p>;
  if (products === null) return <Loading />;
  if (!products.length) return <EmptyState title="Товары появятся здесь после публикации">Откройте каталог позже.</EmptyState>;
  return <div className="grid">{products.map((product) => {
    const item = product as ProductSummaryWithCatalogFields;
    const original = getOriginalPrice(item);
    return <Link href={`/products/${product.slug}`} key={product.id} className="product-card"><ProductImage product={product} /><div className="product-copy"><h3>{product.title}</h3><p>{product.type === "bundle" ? "Комплект" : "Декор для дома"}</p><div className="price-line"><span className="price-stack">{isDiscounted(item) && original && <del className="price-original">{formatMoney(original)}</del>}<strong>{formatMoney(product.price)}</strong></span><span aria-hidden="true">↗</span></div></div></Link>;
  })}</div>;
}
